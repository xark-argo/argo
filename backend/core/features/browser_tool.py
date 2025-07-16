import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional, Union
from urllib.parse import quote, urlencode

import requests
import ua_generator
import urllib3
from bs4 import BeautifulSoup
from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from langchain_core.tools import BaseTool, ToolException

from utils.time_tool import is_in_china


def _handle_browser_error(error: ToolException) -> str:
    result = f"browser tool execute error: {error.args[0]}"
    return result


class BrowserTool(BaseTool):
    name: str = "browser_search"
    description: str = "bing browser search query"
    handle_tool_error: Optional[Union[bool, str, Callable[[ToolException], str]]] = _handle_browser_error
    base_url: str = "https://cn.bing.com/search" if is_in_china() else "https://www.bing.com/search"

    @classmethod
    def from_browser(cls):
        return cls(name="browser_search", description="bing browser search query")

    def bing_search(self, query):
        results = []
        for attempt in range(3):
            try:
                query_url = quote(f"https://cn.bing.com/search?q={query}&count=30", safe="/:?=")
                ua = ua_generator.generate(device="desktop", browser=("chrome", "edge"))
                headers = {"User-Agent": ua.text}
                logging.info(f"BingSearch {query_url}")

                response = requests.get(query_url, headers=headers, timeout=30)
                response.raise_for_status()

                soup = BeautifulSoup(response.content.decode("utf-8"), "html.parser")

                for item in soup.find_all("li", class_="b_algo"):
                    title = item.find("h2")
                    link = item.find("a")
                    snippet = item.find("p")

                    if title and link:
                        result = {
                            "title": title.get_text(),
                            "url": link.get("href", ""),
                            "snippet": snippet.get_text() if snippet else "",
                        }
                        results.append(result)

                if results:
                    return results
            except Exception as ex:
                logging.warning(f"Retry {attempt + 1}/3 due to error: {ex}")
                time.sleep(random.randint(2, 5))
        return results

    def baidu_search(self, query):
        base_url = "https://www.baidu.com/s"
        params = {"wd": query}
        encoded_params = urlencode(params)
        query_url = f"{base_url}?{encoded_params}"

        http = urllib3.PoolManager()
        ua = ua_generator.generate(device="desktop", browser=("chrome", "edge"))
        headers = {"User-Agent": ua.text}

        try:
            response = http.request("GET", query_url, headers=headers)
            if response.status == 200:
                soup = BeautifulSoup(response.data.decode("utf-8"), "html.parser")
                content_div = soup.find("div", id="content_left")
                total_div = content_div.find_all("div", recursive=False)
                results = []
                for div in total_div[:-1]:
                    h3 = div.find("h3")
                    if h3 is None:
                        continue
                    a = h3.find("a")
                    if a is None:
                        continue
                    url = a.get("href", "")
                    title = a.text
                    snippet = h3.find_next_sibling("div")
                    if snippet is None:
                        snippet = ""
                    else:
                        snippet = snippet.get_text().replace("\n", " ").strip()
                    results.append({"url": url, "title": title, "snippet": snippet})
                return results
        except urllib3.exceptions.HTTPError as ex:
            logging.exception("Baidu search failed")
            return []
        except Exception as ex:
            logging.exception("BrowserTool error")
            return []

    def _run(self, query: str, run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        try:
            results = []
            for i in range(3):
                results = self.bing_search(query)
                if not results:
                    results = self.baidu_search(query)
                if results:
                    net_results = ["## search results from the internet"]
                    for each in results:
                        net_results.append(f"- **[{each['title']}]({each['url']})**: {each['snippet']}")
                    return "\n".join(net_results)
                else:
                    logging.info(f"search bing and baidu timeout, retry {i}...")
            return json.dumps(results, ensure_ascii=False)
        except Exception as ex:
            logging.exception("BrowserTool error")
            raise ToolException(str(ex))

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        raise NotImplementedError("browser_search does not support async")


class BrowserUrlTool(BaseTool):
    name: str = "browser_search"
    description: str = "browser url analyse"
    handle_tool_error: Optional[Union[bool, str, Callable[[ToolException], str]]] = _handle_browser_error

    @classmethod
    def from_browser_url(cls):
        return cls(name="browser_url_search", description="browser url parse")

    @staticmethod
    def fetch_url(url):
        try:
            for i in range(3):
                ua = ua_generator.generate(device="desktop", browser=("chrome", "edge"))
                headers = {"User-Agent": ua.text}
                html = requests.get(url, headers=headers, timeout=10)
                if html.status_code == 200:
                    soup = BeautifulSoup(html.content.decode("utf-8"), "html.parser")
                    text = soup.get_text()
                    if text:
                        return text
                logging.info(f"search {url} timeout, retry {i}...")
            return ""
        except Exception as ex:
            return ""

    def _run(self, urls: list[str], run_manager: Optional[CallbackManagerForToolRun] = None) -> str:
        context = ""
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(BrowserUrlTool.fetch_url, url): url for url in urls}
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    data = future.result()
                    context += f"Content from: {url}, Content:\n{data}\n"
                except Exception as ex:
                    logging.exception(f"{url} generated an exception")
                    raise ToolException(str(ex))
        return context

    async def _arun(self, query: str, run_manager: Optional[AsyncCallbackManagerForToolRun] = None) -> str:
        return ""
