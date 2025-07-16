import datetime
import json
import logging
import random
import re
from collections.abc import Callable
from copy import deepcopy
from enum import Enum
from re import Match
from typing import Any, Optional, TypedDict, cast

from core.entities.application_entities import ModelConfigEntity
from core.features.tokenizer import get_token_count
from core.prompt.prompt_template import PromptTemplateParser
from database import db
from models.conversation import Conversation


class ScanState(Enum):
    NONE = 0  # The scan will be stopped.
    INITIAL = 1  # Initial state.
    RECURSION = 2  # The scan is triggered by a recursion step.
    MIN_ACTIVATIONS = 3  # The scan is triggered by a min activations depth skew.


DEFAULT_AMOUNT_GEN = 80
DEFAULT_WORLD_INFO_BUDGET = 25
DEFAULT_DEPTH = 4
MAX_SCAN_DEPTH = 1000
WORLD_INFO_MAX_RECURSION_STEPS = 10
DEFAULT_WEIGHT = 100


class RegexPlacement(Enum):
    MD_DISPLAY = 0
    USER_INPUT = 1
    AI_OUTPUT = 2
    SLASH_COMMAND = 3
    WORLD_INFO = 5


sort_fun = lambda x: -x.order


class WorldInfoLogic(Enum):
    AND_ANY = 0
    NOT_ALL = 1
    NOT_ANY = 2
    AND_ALL = 3


class WorldInfoPosition(Enum):
    Before = 0
    After = 1
    ANTop = 2
    ANBottom = 3
    AtDepth = 4
    EMTop = 5
    EMBottom = 6


class WorldInfoAnchorPosition(Enum):
    Before = 0
    After = 1


class ExtensionPromptRole(Enum):
    SYSTEM = 0
    USER = 1
    ASSISTANT = 2


class WIScanEntry:
    def __init__(
        self,
        scan_depth: Optional[int] = None,
        case_sensitive: Optional[bool] = None,
        match_whole_words: Optional[bool] = None,
        use_group_scoring: Optional[bool] = None,
        uid: Optional[int] = None,
        world: Optional[str] = None,
        key: Optional[list[str]] = None,
        keysecondary: Optional[list[str]] = None,
        selective_logic: Optional[int] = None,
        sticky: Optional[int] = None,
        cooldown: Optional[int] = None,
        delay: Optional[int] = None,
        decorators: Optional[list[str]] = None,
        hash: Optional[int] = None,
        **kwargs,
    ):
        self.scan_depth = scan_depth
        self.case_sensitive = case_sensitive
        self.match_whole_words = match_whole_words
        self.use_group_scoring = use_group_scoring
        self.uid = uid
        self.world = world
        self.key = key or []
        self.keysecondary = keysecondary or []
        self.selective_logic = selective_logic
        self.sticky = sticky
        self.cooldown = cooldown
        self.delay = delay
        self.decorators = decorators or []
        self.hash = hash
        self.role = None
        self.depth = None
        self.position = None
        self.content = None

        for key, value in kwargs.items():  # type: ignore
            setattr(self, key, value)  # type: ignore

    def to_dict(self):
        return self.__dict__


class Macro(TypedDict):
    regex: re.Pattern[str]
    replace: Callable[[Match[str]], str]


def substitute_inputs(inputs: dict[str, str], prompt: Optional[str] = None) -> str:
    if prompt:
        prompt_template = PromptTemplateParser(template=prompt)
        for name in prompt_template.variable_keys:
            val = inputs.get(name, inputs.get(name.lower(), ""))
            prompt = prompt.replace(f"{{{{{name}}}}}", str(val))

    def get_random_replace_macro() -> Macro:
        random_pattern = re.compile(r"{{random\s*::?([^}]+)}}", re.IGNORECASE)

        def random_replace(match: Match[str]) -> str:
            list_string = match.group(1)
            if "::" in list_string:
                lst = list_string.split("::")
            else:
                lst = [
                    item.strip().replace("##�COMMA�##", ",")
                    for item in list_string.replace(r"\,", "##�COMMA�##").split(",")
                ]
            return random.choice(lst) if lst else ""

        return {"regex": random_pattern, "replace": random_replace}

    def make_macro(regex: str, func: Callable[[Match[str]], str], flags=0) -> Macro:
        return {"regex": re.compile(regex, flags), "replace": func}

    pre_env_macros: list[Macro] = [
        make_macro(r"<USER>", lambda m: inputs.get("user", ""), re.IGNORECASE),
        make_macro(r"<BOT>", lambda m: inputs.get("char", ""), re.IGNORECASE),
        make_macro(r"{{newline}}", lambda m: "\n", re.IGNORECASE),
        make_macro(r"(?:\r?\n)*{{trim}}(?:\r?\n)*", lambda m: "", re.IGNORECASE),
        make_macro(r"{{noop}}", lambda m: "", re.IGNORECASE),
    ]

    now = datetime.datetime.now()
    post_env_macros: list[Macro] = [
        make_macro(r"{{time}}", lambda m: now.strftime("%I:%M %p"), re.IGNORECASE),
        make_macro(r"{{date}}", lambda m: now.strftime("%B %d, %Y"), re.IGNORECASE),
        make_macro(r"{{weekday}}", lambda m: now.strftime("%A"), re.IGNORECASE),
        make_macro(r"{{isotime}}", lambda m: now.strftime("%H:%M"), re.IGNORECASE),
        make_macro(r"{{isodate}}", lambda m: now.strftime("%Y-%m-%d"), re.IGNORECASE),
        make_macro(r"{{reverse:(.+?)}}", lambda m: m.group(1)[::-1], re.IGNORECASE),
        make_macro(r"\{\{//([\s\S]*?)\}\}", lambda m: "", re.MULTILINE),
        get_random_replace_macro(),
    ]

    macros = pre_env_macros + post_env_macros

    def apply_macro(prompt_str: str, macro: Macro) -> str:
        try:
            return re.sub(macro["regex"], macro["replace"], prompt_str)
        except Exception as e:
            logging.warning(f"Macro content can't be replaced: {macro['regex']} in {prompt_str}, Error: {e}")
            return prompt_str

    for macro in macros:
        if not prompt:
            break
        if not macro["regex"].pattern.startswith("<") and "{{" not in prompt:
            break
        prompt = apply_macro(prompt, macro)

    return cast(str, prompt)


def extract_character_regex_scripts(inputs: dict) -> list:
    character_book = json.loads(inputs["character_extensions"])

    return [
        {
            "script_name": script.get("scriptName"),
            "find_regex": script.get("findRegex"),
            "replace_string": script.get("replaceString"),
            "trim_strings": script.get("trimStrings", []),
            "placement": script.get("placement", []),
            "disabled": script.get("disabled", False),
            "markdown_only": script.get("markdownOnly", False),
            "prompt_only": script.get("promptOnly", False),
            "run_on_edit": script.get("runOnEdit", False),
            "substitute_regex": script.get("substituteRegex", False),
            "min_depth": int(script["minDepth"]) if script.get("minDepth") else None,
            "max_depth": int(script["maxDepth"]) if script.get("minDepth") else None,
            "id": script.get("id"),
        }
        for script in character_book.get("regex_scripts", [])
    ]


def extract_world_info_books(inputs: dict[str, str]) -> dict:
    world_info_books: dict[str, Any] = {}
    try:
        if inputs.get("character_book"):
            character_book = json.loads(inputs["character_book"])
            world_info_books["character_books"] = convert_world_info_book(character_book)
        if inputs.get("persona_book"):
            persona_book = json.loads(inputs["persona_book"])
            world_info_books["persona_books"] = convert_world_info_book(persona_book)
    except Exception as e:
        raise Exception(f"Failed extract world info books. error: {e}")

    return world_info_books


def convert_world_info_book(world_info_book):
    entries: list[WIScanEntry] = []
    name = world_info_book.get("name")

    if not isinstance(world_info_book.get("entries"), list):
        return {"name": name, "entries": entries}

    for index, entry in enumerate(world_info_book.get("entries", [])):
        if "id" not in entry or entry["id"] is None:
            entry["id"] = index

        extensions = entry.get("extensions", {})

        new_entry = {
            "uid": entry["id"],
            "world": name,
            "key": entry.get("keys", []),
            "keysecondary": entry.get("secondary_keys", []),
            "comment": entry.get("comment", ""),
            "content": entry.get("content", ""),
            "constant": entry.get("constant", False),
            "selective": entry.get("selective", True),
            "order": entry.get("insertion_order", 100),
            "position": extensions.get("position")
            or (
                WorldInfoPosition.Before.value
                if entry.get("position") == "before_char"
                else WorldInfoPosition.After.value
            ),
            "exclude_recursion": extensions.get("exclude_recursion", False),
            "prevent_recursion": extensions.get("prevent_recursion", False),
            "delay_until_recursion": extensions.get("delay_until_recursion", False),
            "disable": not entry.get("enabled", True),
            "add_memo": bool(entry.get("comment")),
            "display_index": extensions.get("display_index", index),
            "probability": extensions.get("probability", 100),
            "use_probability": extensions.get("useProbability", True),
            "depth": extensions.get("depth", DEFAULT_DEPTH),
            "selective_logic": extensions.get("selectiveLogic", WorldInfoLogic.AND_ANY.value),
            "group": extensions.get("group", ""),
            "group_override": extensions.get("group_override", False),
            "group_weight": extensions.get("group_weight", DEFAULT_WEIGHT),
            "scan_depth": extensions.get("scan_depth"),
            "case_sensitive": extensions.get("case_sensitive"),
            "match_whole_words": extensions.get("match_whole_words"),
            "use_group_scoring": extensions.get("use_group_scoring"),
            "automation_id": extensions.get("automation_id", ""),
            "role": extensions.get("role", ExtensionPromptRole.SYSTEM.value),
            "vectorized": extensions.get("vectorized", False),
            "sticky": extensions.get("sticky"),
            "cooldown": extensions.get("cooldown"),
            "delay": extensions.get("delay"),
            "extensions": extensions,
        }

        entries.append(WIScanEntry(**new_entry))

    return {"name": name, "entries": entries}


def get_world_info_prompt(
    model_config: ModelConfigEntity,
    max_context: int,
    conversation: Conversation,
    messages: list[str],
    inputs: dict[str, str],
):
    try:
        activated_world_info = check_world_info(model_config, max_context, conversation, messages, inputs)
        return {
            "em_entries": activated_world_info.get("em_entries", []),
            "world_info_before": activated_world_info.get("world_info_before", ""),
            "world_info_after": activated_world_info.get("world_info_after", ""),
            "world_info_depth": activated_world_info.get("wi_depth_entries", []),
        }
    except Exception as e:
        raise Exception(f"Failed to retrieve activated world information. error: {e}")


def check_world_info(
    model_config: ModelConfigEntity,
    max_context: int,
    conversation: Conversation,
    messages: list[str],
    inputs: dict[str, str],
):
    buffer = WorldInfoBuffer(messages)

    budget = round(DEFAULT_WORLD_INFO_BUDGET * max_context / 100) if DEFAULT_WORLD_INFO_BUDGET and max_context else 1

    world_info_books = extract_world_info_books(inputs)
    regex_scripts = extract_character_regex_scripts(inputs)

    logging.info(f"[WI] Context size: {max_context}; WI budget: {budget} (max% = {DEFAULT_WORLD_INFO_BUDGET}%)")

    sorted_entries = get_sorted_entries(world_info_books)
    if len(sorted_entries) == 0:
        return {
            "world_info_before": "",
            "world_info_after": "",
            "wi_depth_entries": [],
            "em_entries": [],
        }

    timed_effects = WorldInfoTimedEffects(conversation, messages, sorted_entries)
    timed_effects.check_timed_effects()

    recursion_delays = [
        1 if entry.delay_until_recursion is True else entry.delay_until_recursion
        for entry in sorted_entries
        if entry.delay_until_recursion
    ]
    available_recursion_delay_levels = sorted(set(recursion_delays))

    current_recursion_delay_level = available_recursion_delay_levels.pop(0) if available_recursion_delay_levels else 0

    if current_recursion_delay_level > 0 and available_recursion_delay_levels:
        logging.info(
            "[WI] Preparing first delayed recursion level",
            current_recursion_delay_level,
            ". Still delayed:",
            available_recursion_delay_levels,
        )

    logging.info(f"[WI] --- SEARCHING ENTRIES (on {len(sorted_entries)} entries) ---")

    count = 0
    scan_state = ScanState.INITIAL
    all_activated_entries: dict[str, WIScanEntry] = {}
    failed_probability_checks: set[str] = set()
    token_budget_overflowed = False
    all_activated_text = ""

    while scan_state.value:
        if WORLD_INFO_MAX_RECURSION_STEPS and count >= WORLD_INFO_MAX_RECURSION_STEPS:
            logging.info(f"[WI] Search stopped by reaching max recursion steps {WORLD_INFO_MAX_RECURSION_STEPS}")
            break

        count += 1

        logging.info(f"[WI] --- LOOP #{count} START ---")
        logging.info(f"[WI] Scan state {scan_state.name}: {scan_state.value}")

        next_scan_state = ScanState.NONE
        activated_now = []

        for entry in sorted_entries:
            header_logged = False

            def log(*args, entry=entry):
                nonlocal header_logged
                if not header_logged:
                    logging.debug(f"[WI] Entry {entry.uid} from '{entry.world}' processing \n{entry.to_dict()}")
                    header_logged = True
                logging.info(f"[WI] Entry {entry.uid} {' '.join(map(str, args))}")

            if entry.hash in failed_probability_checks or f"{entry.world}.{entry.uid}" in all_activated_entries:
                continue

            if entry.disable:
                log("disabled")
                continue

            is_sticky = timed_effects.is_effect_active("sticky", entry)
            is_cooldown = timed_effects.is_effect_active("cooldown", entry)
            is_delay = timed_effects.is_effect_active("delay", entry)

            if is_delay:
                log("suppressed by delay")
                continue

            if is_cooldown and not is_sticky:
                log("suppressed by cooldown")
                continue

            if scan_state != ScanState.RECURSION and entry.delay_until_recursion and not is_sticky:
                log("suppressed by delay until recursion")
                continue

            if (
                scan_state == ScanState.RECURSION
                and entry.delay_until_recursion
                and entry.delay_until_recursion > current_recursion_delay_level
                and not is_sticky
            ):
                log(
                    "suppressed by delay until recursion level",
                    entry.delay_until_recursion,
                    ". Currently",
                    current_recursion_delay_level,
                )
                continue

            if scan_state == scan_state.RECURSION and entry.exclude_recursion and not is_sticky:
                log("suppressed by exclude recursion")
                continue

            if "@@activate" in entry.decorators:
                log("activated by @@activate decorator")
                activated_now.append(entry)
                continue

            if "@@dont_activate" in entry.decorators:
                log("suppressed by @@dont_activate decorator")
                continue

            if entry.constant:
                log("activated because of constant")
                activated_now.append(entry)
                continue

            if is_sticky:
                log("activated because active sticky")
                activated_now.append(entry)
                continue

            if not isinstance(entry.key, list) or not entry.key:
                log("has no keys defined, skipped")
                continue

            text_to_scan = buffer.get(entry, scan_state)

            primary_key_match = None
            for key in entry.key:
                substituted = substitute_inputs(inputs, key)
                if substituted and buffer.match_keys(text_to_scan, substituted.strip(), entry):
                    primary_key_match = key
                    break

            if not primary_key_match:
                continue

            has_secondary_keywords = (
                entry.selective and isinstance(entry.keysecondary, list) and len(entry.keysecondary) > 0
            )

            if not has_secondary_keywords:
                log("activated by primary key match")
                activated_now.append(entry)
                continue

            selective_logic = entry.selective_logic if hasattr(entry, "selective_logic") else 0  # Default to AND (0)

            # log('Entry with primary key match', primary_key_match,
            # 'has secondary keywords. Checking with logic logic', selective_logic)

            def match_secondary_keys(entry=entry, selective_logic=selective_logic, text_to_scan=text_to_scan):
                has_any_match = False
                has_all_match = True
                for keysecondary in entry.keysecondary:
                    secondary_substituted = keysecondary
                    has_secondary_match = secondary_substituted and buffer.match_keys(
                        text_to_scan, secondary_substituted.strip(), entry
                    )

                    if has_secondary_match:
                        has_any_match = True
                    if not has_secondary_match:
                        has_all_match = False

                    if selective_logic == WorldInfoLogic.AND_ANY.value and has_secondary_match:
                        # log('activated. (AND ANY) Found match secondary keyword', secondary_substituted)
                        return True
                    if selective_logic == WorldInfoLogic.NOT_ALL.value and not has_secondary_match:
                        # log('activated. (NOT ALL) Found not matching secondary keyword', secondary_substituted)
                        return True

                if selective_logic == WorldInfoLogic.NOT_ANY.value and not has_any_match:
                    # log('activated. (NOT ANY) No secondary keywords found', entry.keysecondary)
                    return True

                if selective_logic == WorldInfoLogic.AND_ALL.value and has_all_match:
                    # log('activated. (AND ALL) All secondary keywords found', entry.keysecondary)
                    return True

                return False

            matched = match_secondary_keys()
            if not matched:
                # log('skipped. Secondary keywords not satisfied', entry.keysecondary)
                continue

            activated_now.append(entry)
            continue

        logging.info(f"[WI] Search done. Found {len(activated_now)} possible entries.")

        new_entries = sorted(
            activated_now,
            key=lambda entry: (
                -1 if timed_effects.is_effect_active("sticky", entry) else 0,
                sorted_entries.index(entry),
            ),
        )

        logging.info("[WI] --- PROBABILITY CHECKS ---")
        if not new_entries:
            logging.info("[WI] No probability checks to do")

        failed_probability_checks = set()
        new_content = ""
        text_to_scan_tokens = get_token_count(all_activated_text, model_config)

        for entry in new_entries:

            def verify_probability(entry=entry, failed_probability_checks=None):
                if failed_probability_checks is None:
                    failed_probability_checks = failed_probability_checks

                if not entry.use_probability or entry.probability == 100:
                    logging.info(f"WI entry {entry.uid} does not use probability")
                    return True

                is_sticky = timed_effects.is_effect_active("sticky", entry)
                if is_sticky:
                    logging.info(f"WI entry {entry.uid} is sticky, does not need to re-roll probability")
                    return True

                roll_value = random.random() * 100
                if roll_value <= entry.probability:
                    logging.info(f"WI entry {entry.uid} passed probability check of {entry.probability}%")
                    return True

                failed_probability_checks.add(entry.hash)
                return False

            success = verify_probability()
            if not success:
                logging.info(f"WI entry {entry.uid} failed probability check, removing from activated entries")
                continue

            entry.content = substitute_inputs(inputs, entry.content)
            new_content += f"{entry.content}\n"

            if text_to_scan_tokens + get_token_count(new_content, model_config) >= budget:
                logging.info(f"[WI] budget of {budget} reached, stopping after {len(all_activated_entries)} entries")
                token_budget_overflowed = True
                break

            all_activated_entries[f"{entry.world}.{entry.uid}"] = entry
            logging.info(f"[WI] Entry {entry.uid} activation successful, adding to prompt")

        successful_new_entries = [x for x in new_entries if x.hash not in failed_probability_checks]
        successful_new_entries_for_recursion = [x for x in successful_new_entries if not x.prevent_recursion]

        logging.info(f"[WI] --- LOOP #{count} RESULT ---")

        if not new_entries:
            logging.info("[WI] No new entries activated.")
        elif not successful_new_entries:
            logging.info("[WI] Probability checks failed for all activated entries. No new entries activated.")
        else:
            logging.info(
                f"[WI] Successfully activated {len(successful_new_entries)} "
                f"new entries to prompt. {len(all_activated_entries)} total entries activated."
            )

        def log_next_state(*args, state=scan_state):
            if args:
                logging.info(args[0], *args[1:])
            logging.info(f"[WI] Setting scan state {state.name}: {state.value}")

        if not token_budget_overflowed and successful_new_entries_for_recursion:
            next_scan_state = ScanState.RECURSION
            log_next_state(f"[WI] Found {len(successful_new_entries_for_recursion)} new entries for recursion")

        if not token_budget_overflowed and scan_state == ScanState.MIN_ACTIVATIONS and buffer.has_recurse():
            next_scan_state = ScanState.RECURSION
            log_next_state("[WI] Min Activations run done, this will always be followed by a recursive scan")

        if next_scan_state == ScanState.NONE and available_recursion_delay_levels:
            next_scan_state = ScanState.RECURSION
            current_recursion_delay_level = available_recursion_delay_levels.pop(0)
            log_next_state(
                f"[WI] Open delayed recursion levels left. Preparing next delayed \
                recursion level {current_recursion_delay_level}. Still delayed: {available_recursion_delay_levels}"
            )

        scan_state = next_scan_state
        if scan_state:
            text = "\n".join(x.content for x in successful_new_entries_for_recursion)
            buffer.add_recurse(text)
            all_activated_text = f"{text}\n{all_activated_text}"
        else:
            log_next_state("[WI] Scan done. No new entries to prompt. Stopping.")

    logging.debug("[WI] --- BUILDING PROMPT ---")

    wi_before_entries: list[str] = []
    wi_after_entries: list[str] = []
    em_entries: list[dict[str, Any]] = []
    an_top_entries: list[str] = []
    an_bottom_entries: list[str] = []
    wi_depth_entries: list[dict[str, Any]] = []

    for entry in sorted(all_activated_entries.values(), key=sort_fun):
        regex_depth = None
        if entry.position == WorldInfoPosition.AtDepth.value:
            if entry.depth:
                regex_depth = entry.depth
            else:
                regex_depth = DEFAULT_DEPTH

        content = get_regexed_string(
            entry.content,
            RegexPlacement.WORLD_INFO,
            regex_scripts,
            inputs,
            depth=regex_depth,
            is_markdown=False,
            is_prompt=True,
        )

        if not content:
            logging.debug(f"[WI] Entry {entry.uid} skipped adding to prompt due to empty content")
            continue

        if entry.position == WorldInfoPosition.Before.value:
            wi_before_entries.insert(0, content)
        elif entry.position == WorldInfoPosition.After.value:
            wi_after_entries.insert(0, content)
        elif entry.position == WorldInfoPosition.EMTop.value:
            em_entries.insert(
                0,
                {"position": WorldInfoAnchorPosition.Before.value, "content": content},
            )
        elif entry.position == WorldInfoPosition.EMBottom.value:
            em_entries.insert(0, {"position": WorldInfoAnchorPosition.After.value, "content": content})
        elif entry.position == WorldInfoPosition.ANTop.value:
            an_top_entries.insert(0, content)
        elif entry.position == WorldInfoPosition.ANBottom.value:
            an_bottom_entries.insert(0, content)
        elif entry.position == WorldInfoPosition.AtDepth.value:
            existing_depth_index = next(
                (
                    i
                    for i, e in enumerate(wi_depth_entries)
                    if e["depth"] == (entry.depth if entry.depth is not None else DEFAULT_DEPTH)
                    and e["role"] == (entry.role if entry.role is not None else ExtensionPromptRole.SYSTEM.value)
                ),
                -1,
            )
            if existing_depth_index != -1:
                wi_depth_entries[existing_depth_index]["entries"].insert(0, content)
            else:
                wi_depth_entries.append(
                    {
                        "depth": entry.depth,
                        "entries": [content],
                        "role": (entry.role or ExtensionPromptRole.SYSTEM.value),
                    }
                )

    world_info_before = "\n".join(wi_before_entries) if wi_before_entries else ""
    world_info_after = "\n".join(wi_after_entries) if wi_after_entries else ""

    timed_effects.set_timed_effects(list(all_activated_entries.values()))
    buffer.reset_external_effects()
    timed_effects.clean_up()

    logging.info(f"[WI] Adding {len(all_activated_entries)} entries to prompt")
    logging.info("[WI] --- DONE ---")

    return {
        "world_info_before": world_info_before,
        "world_info_after": world_info_after,
        "em_entries": em_entries,
        "wi_depth_entries": wi_depth_entries,
        "all_activated_entries": set(all_activated_entries.values()),
    }


def get_sorted_entries(world_info_books: dict):
    character_lore = get_character_lore(world_info_books.get("character_books", {}))
    persona_lore = get_persona_lore(world_info_books.get("persona_books", {}))

    entries = [
        *sorted(persona_lore, key=sort_fun),
        *sorted(character_lore, key=sort_fun),
    ]

    for entry in entries:
        decorators, content = parse_decorators(entry.content)
        entry.content = content
        entry.decorators = decorators

        entry_json = json.dumps(entry.to_dict(), sort_keys=True)
        hash_value = get_string_hash(entry_json)
        entry.hash = hash_value

    logging.info(f"[WI] Found {len(entries)} world lore entries")
    return entries


def get_character_lore(character_book: dict) -> list[WIScanEntry]:
    name = character_book.get("name")
    entries = character_book.get("entries", [])
    logging.info(f"[WI] Character {name}'s lore has {len(entries)} world info entries")
    return cast(list[WIScanEntry], entries)


def get_persona_lore(persona_book: dict) -> list[WIScanEntry]:
    name = persona_book.get("name")
    entries = persona_book.get("entries", [])
    logging.info(f"[WI] Character {name}'s lore has {len(entries)} world info entries")
    return cast(list[WIScanEntry], entries)


def parse_regex_from_string(input_str):
    match = re.match(r"^/([\w\W]+?)/([gimsuy]*)$", input_str)
    if not match:
        return None

    pattern, flags = match.groups()

    if re.search(r"(^|[^\\])/", pattern):
        return None

    pattern = pattern.replace(r"\/", "/")
    pattern = pattern.replace("[^]*", ".*")

    flag_map = {
        "g": 0,
        "i": re.IGNORECASE,
        "m": re.MULTILINE,
        "s": re.DOTALL,
        "u": re.UNICODE,
        "y": 0,
    }

    re_flags = 0
    for flag in flags:
        re_flags |= flag_map.get(flag, 0)

    try:
        return re.compile(pattern, re_flags)
    except re.error:
        return None


def get_string_hash(s, seed=0):
    if not isinstance(s, str):
        return 0

    h1 = 0xDEADBEEF ^ seed
    h2 = 0x41C6CE57 ^ seed

    for ch in s:
        ch_code = ord(ch)
        h1 = (h1 ^ ch_code) * 2654435761 & 0xFFFFFFFF
        h2 = (h2 ^ ch_code) * 1597334677 & 0xFFFFFFFF

    h1 = (h1 ^ (h1 >> 16)) * 2246822507 & 0xFFFFFFFF ^ (h2 ^ (h2 >> 13)) * 3266489909 & 0xFFFFFFFF
    h2 = (h2 ^ (h2 >> 16)) * 2246822507 & 0xFFFFFFFF ^ (h1 ^ (h1 >> 13)) * 3266489909 & 0xFFFFFFFF

    return 4294967296 * (h2 & 0x1FFFFF) + (h1 & 0xFFFFFFFF)


KNOWN_DECORATORS = ["@@activate", "@@dont_activate"]


def parse_decorators(content):
    def is_known_decorator(data):
        if data.startswith("@@@"):
            data = data[1:]
        return any(data.startswith(decorator) for decorator in KNOWN_DECORATORS)

    if content.startswith("@@"):
        new_content = content
        splited = content.split("\n")
        decorators = []
        fallbacked = False

        for i, line in enumerate(splited):
            if line.startswith("@@"):
                if line.startswith("@@@") and not fallbacked:
                    continue

                if is_known_decorator(line):
                    decorators.append(line[1:] if line.startswith("@@@") else line)
                    fallbacked = False
                else:
                    fallbacked = True
            else:
                new_content = "\n".join(splited[i:])
                break

        return decorators, new_content

    return [], content


def escape_regex(string: str) -> str:
    return re.sub(r"[/\-\\^$*+?.()|[\]{}]", r"\\\g<0>", string)


def get_regexed_string(
    raw_string: str,
    placement: RegexPlacement,
    regex_scripts: list,
    inputs: dict[str, str],
    is_markdown=False,
    is_prompt=False,
    is_edit=False,
    depth=None,
):
    final_string = raw_string
    if not raw_string or placement is None or len(regex_scripts) == 0:
        return final_string

    for script in regex_scripts:
        if (
            (script.get("markdown_only") and is_markdown)
            or (script.get("prompt_only") and is_prompt)
            or (not script.get("markdown_only") and not script.get("prompt_only") and not is_markdown)
        ):
            if is_edit and not script.get("run_on_edit"):
                continue

            if depth and depth >= 0:
                if script.get("min_depth") and depth < script["min_depth"]:
                    continue

                if script.get("max_depth") and depth > script["max_depth"]:
                    continue

            # if placement.value in script.get('placement', []):
            final_string = run_regex_script(script, final_string, inputs)

    return final_string


def run_regex_script(regex_script, raw_string, inputs: dict[str, str]):
    new_string = raw_string
    if not raw_string or not regex_script or regex_script.get("disabled") or not regex_script.get("find_regex"):
        return new_string

    def regex_from_string(input_str):
        try:
            m = re.match(r"(\/?)(.+)\1([a-z]*)", input_str, re.IGNORECASE)

            if not m:
                return None

            pattern = m.group(2)
            flags_str = m.group(3)

            if flags_str and not re.match(r"^(?!.*?(.).*?\1)[gmixXsuUAJ]+$", flags_str):
                return re.compile(input_str)

            flag_map = {
                "g": 0,
                "i": re.IGNORECASE,
                "m": re.MULTILINE,
                "s": re.DOTALL,
                "x": re.VERBOSE,
                "u": 0,
                "A": re.ASCII,
                "J": 0,
            }

            flags = 0
            for flag in flags_str:
                flags |= flag_map.get(flag, 0)

            return re.compile(pattern, flags)

        except Exception:
            return None

    regex_string = regex_script["find_regex"]
    find_regex = regex_from_string(regex_string)

    if not find_regex:
        return new_string

    def filter_string(raw_string, trim_strings):
        final_string = raw_string
        for trim_string in trim_strings:
            sub_trim_string = substitute_inputs(inputs, trim_string)
            final_string = final_string.replace(sub_trim_string, "")
        return final_string

    def replacement_function(match):
        replace_string = regex_script.get("replace_string", "").replace("{{match}}", match.group(0))

        def replace_with_groups(m):
            num = int(m.group(1))
            match_group = match.group(num) if 1 <= num <= len(match.groups()) else ""
            return filter_string(match_group, regex_script.get("trim_strings", []))

        replace_with_groups_result = re.sub(r"\$(\d+)", replace_with_groups, replace_string)
        return substitute_inputs(inputs, replace_with_groups_result)

    new_string = find_regex.sub(replacement_function, raw_string)

    return new_string


class WorldInfoBuffer:
    external_activations: dict[str, object] = {}

    def __init__(self, messages: list[str]):
        self._depth_buffer: list[str] = []
        self._recurse_buffer: list[str] = []
        self._inject_buffer: list[str] = []
        self._skew = 0
        self._start_depth = 0
        self.world_info_depth = 2
        self._init_depth_buffer(messages)

    def _init_depth_buffer(self, messages: list[str]):
        for depth in range(MAX_SCAN_DEPTH):
            if depth < len(messages):
                self._depth_buffer.append(messages[depth].strip())
            if depth == len(messages) - 1:
                break

    def _transform_string(self, text, entry) -> str:
        case_sensitive = entry.case_sensitive if entry.case_sensitive is not None else False
        return str(text) if case_sensitive else text.lower()

    def get(self, entry, scan_state) -> str:
        depth = entry.scan_depth if entry.scan_depth is not None else self.get_depth()
        if depth <= self._start_depth:
            return ""

        if depth < 0:
            logging.info(f"[WI] Invalid WI scan depth {depth}. Must be >= 0")
            return ""

        if depth > MAX_SCAN_DEPTH:
            logging.info(f"[WI] Invalid WI scan depth {depth}. Truncating to {MAX_SCAN_DEPTH}")
            depth = MAX_SCAN_DEPTH

        matcher = "\x01"
        joiner = "\n" + matcher
        result = matcher + joiner.join(self._depth_buffer[self._start_depth : depth])

        if self._inject_buffer:
            result += joiner + joiner.join(self._inject_buffer)

        if self._recurse_buffer and scan_state != ScanState.MIN_ACTIVATIONS:
            result += joiner + joiner.join(self._recurse_buffer)

        return result

    def match_keys(self, haystack, needle, entry) -> bool:
        key_regex = parse_regex_from_string(needle)
        if key_regex:
            return bool(key_regex.search(haystack))

        haystack = self._transform_string(haystack, entry)
        transformed_string = self._transform_string(needle, entry)
        match_whole_words = entry.match_whole_words if entry.match_whole_words is not None else False

        if match_whole_words:
            key_words = transformed_string.split()
            if len(key_words) > 1:
                return transformed_string in haystack
            else:
                regex = re.compile(r"(?:^|\W)(" + escape_regex(transformed_string) + r")(?:$|\W)")
                return bool(regex.search(haystack))
        else:
            return bool(haystack.find(transformed_string) != -1)

    def add_recurse(self, message: str):
        self._recurse_buffer.append(message)

    def add_inject(self, message: str):
        self._inject_buffer.append(message)

    def has_recurse(self) -> bool:
        return len(self._recurse_buffer) > 0

    def advance_scan(self):
        self._skew += 1

    def get_depth(self) -> int:
        return self.world_info_depth + self._skew

    def get_externally_activated(self, entry) -> Optional[object]:
        return WorldInfoBuffer.external_activations.get(f"{entry.world}.{entry.uid}")

    def reset_external_effects(self):
        WorldInfoBuffer.external_activations = {}

    def get_score(self, entry, scan_state: int) -> int:
        buffer_state = self.get(entry, scan_state)
        number_of_primary_keys = 0
        number_of_secondary_keys = 0
        primary_score = 0
        secondary_score = 0

        if isinstance(entry.key, list):
            number_of_primary_keys = len(entry.key)
            for key in entry.key:
                if self.match_keys(buffer_state, key, entry):
                    primary_score += 1

        if isinstance(entry.keysecondary, list):
            number_of_secondary_keys = len(entry.keysecondary)
            for key in entry.keysecondary:
                if self.match_keys(buffer_state, key, entry):
                    secondary_score += 1

        if not number_of_primary_keys:
            return 0

        if number_of_secondary_keys > 0:
            if entry.selective_logic == WorldInfoLogic.AND_ANY.value:
                return primary_score + secondary_score
            elif entry.selective_logic == WorldInfoLogic.AND_ALL.value:
                return primary_score + secondary_score if secondary_score == number_of_secondary_keys else primary_score

        return primary_score


class WorldInfoTimedEffects:
    def __init__(self, conversation: Conversation, messages: list[str], entries):
        self._chat_messages = messages
        self._conversation = conversation
        self._chat_metadata = deepcopy(conversation.chat_metadata)
        self._entries = entries
        self._buffer: dict[str, Any] = {effect: [] for effect in ["sticky", "cooldown", "delay"]}
        self._on_ended = {
            "sticky": self.on_sticky_ended,
            "cooldown": self.on_cooldown_ended,
            "delay": lambda entry: None,
        }
        self._ensure_chat_metadata()

    def _ensure_chat_metadata(self):
        self._chat_metadata.setdefault("timed_world_info", {})
        for effect_type in ["sticky", "cooldown"]:
            self._chat_metadata["timed_world_info"].setdefault(effect_type, {})
            for key, value in list(self._chat_metadata["timed_world_info"][effect_type].items()):
                if not value or not isinstance(value, dict):
                    del self._chat_metadata["timed_world_info"][effect_type][key]

    def get_entry_hash(self, entry):
        return entry.hash

    def get_entry_key(self, entry):
        return f"{entry.world}.{entry.uid}"

    def get_entry_timed_effect(self, effect_type, entry, is_protected):
        return {
            "hash": self.get_entry_hash(entry),
            "start": len(self._chat_messages),
            "end": len(self._chat_messages) + int(getattr(entry, effect_type)),
            "protected": bool(is_protected),
        }

    def on_sticky_ended(self, entry):
        if not entry.cooldown:
            return

        key = self.get_entry_key(entry)
        effect = self.get_entry_timed_effect("cooldown", entry, True)
        self._chat_metadata["timed_world_info"]["cooldown"][key] = effect
        logging.info(
            f"[WI] Adding cooldown entry {key} on ended sticky: start={effect['start']}, \
            end={effect['end']}, protected={effect['protected']}"
        )
        self._buffer["cooldown"].append(entry)

    def on_cooldown_ended(self, entry):
        logging.info(f"[WI] Cooldown ended for entry {entry.uid}")

    def check_timed_effect_of_type(self, effect_type, buffer, on_ended):
        effects = list(self._chat_metadata["timed_world_info"][effect_type].items())
        for key, value in effects:
            logging.info(f"[WI] Processing {effect_type} entry {key} \n{value}")
            entry = next(
                (x for x in self._entries if str(self.get_entry_hash(x)) == str(value["hash"])),
                None,
            )

            if len(self._chat_messages) <= int(value["start"]) and not value["protected"]:
                logging.info(f"[WI] Removing {effect_type} entry {key} from timed_world_info: chat not advanced")
                del self._chat_metadata["timed_world_info"][effect_type][key]
                continue

            if not entry:
                if len(self._chat_messages) >= int(value["end"]):
                    logging.info(
                        f"[WI] Removing {effect_type} entry from timedWorldInfo: entry not found and interval passed"
                    )
                    del self._chat_metadata["timed_world_info"][effect_type][key]
                continue

            if not getattr(entry, effect_type):
                logging.info(f"[WI] Removing {effect_type} entry from timedWorldInfo: entry not {effect_type}")
                del self._chat_metadata["timed_world_info"][effect_type][key]
                continue

            if len(self._chat_messages) >= int(value["end"]):
                logging.info(f"[WI] Removing {effect_type} entry from timedWorldInfo: {effect_type} interval passed")
                del self._chat_metadata["timed_world_info"][effect_type][key]
                if callable(on_ended):
                    on_ended(entry)
                continue

            buffer.append(entry)
            logging.info(f'[WI] Timed effect "{effect_type}" applied to entry')

    def check_delay_effect(self, buffer):
        for entry in self._entries:
            if not entry.delay:
                continue

            if len(self._chat_messages) < entry.delay:
                buffer.append(entry)
                logging.info(f'[WI] Timed effect "delay" applied to entry {entry.uid}')

    def check_timed_effects(self):
        self.check_timed_effect_of_type("sticky", self._buffer["sticky"], self._on_ended["sticky"])
        self.check_timed_effect_of_type("cooldown", self._buffer["cooldown"], self._on_ended["cooldown"])
        self.check_delay_effect(self._buffer["delay"])

    def get_effect_metadata(self, effect_type, entry):
        if not self.is_valid_effect_type(effect_type):
            return None
        key = self.get_entry_key(entry)
        return self._chat_metadata["timed_world_info"].get(effect_type, {}).get(key)

    def is_valid_effect_type(self, effect_type):
        return isinstance(effect_type, str) and effect_type.strip().lower() in [
            "sticky",
            "cooldown",
            "delay",
        ]

    def set_timed_effects(self, activated_entries):
        for entry in activated_entries:
            self.set_timed_effect_of_type("sticky", entry)
            self.set_timed_effect_of_type("cooldown", entry)

    def set_timed_effect_of_type(self, effect_type, entry):
        if not getattr(entry, effect_type, None):
            return

        key = self.get_entry_key(entry)

        if key not in self._chat_metadata["timed_world_info"][effect_type]:
            effect = self.get_entry_timed_effect(effect_type, entry, False)
            self._chat_metadata["timed_world_info"][effect_type][key] = effect
            logging.info(
                f"[WI] Adding {effect_type} entry {key}: start={effect['start']}, \
                end={effect['end']}, protected={effect['protected']}"
            )

    def is_effect_active(self, effect_type, entry):
        if not self.is_valid_effect_type(effect_type):
            return False

        return any(self.get_entry_hash(x) == self.get_entry_hash(entry) for x in self._buffer.get(effect_type, []))

    def clean_up(self):
        with db.session_scope() as session:
            session.query(Conversation).filter_by(id=self._conversation.id).update(
                {Conversation.chat_metadata: self._chat_metadata}
            )
            session.commit()

        for buffer in self._buffer.values():
            buffer.clear()
