from typing import Optional, Union

from pydantic import BaseModel, Field


class ResponsePayload(BaseModel):
    """A model creation request"""

    status: Union[str, int, None] = Field(None, description="The status of the request")
    error: Optional[str] = Field(None, description="The error of the request")
    digest: Optional[str] = Field(None, description="The digest of the model")
    total: Optional[int] = Field(0, description="The total number of models")
    completed: Optional[int] = Field(0, description="The number of completed models")


class ModelDetails(BaseModel):
    """Details about a model"""

    format: str = Field(..., description="The format of the model")
    parameter_size: str = Field(..., description="The parameter size of the model")
    quantization_level: str = Field(..., description="The quantization level of the model")


class ModelInfo(BaseModel):
    """Info about a model"""

    general_architecture: Optional[str] = Field(None, alias="general.architecture")


class ModelTag(BaseModel):
    """Information about the model"""

    name: str = Field(..., description="The name of the model")
    digest: str = Field(..., description="The digest of the model")
    size: int = Field(..., description="The size of the model in bytes")
    modified_at: str = Field(..., description="The time the model was created")
    details: ModelDetails = Field(..., description="Details about the model")
    template: Optional[str] = Field(None, description="The template of the model")
    parameters: Optional[str] = Field(None, description="The parameters of the model")
    model_info: Optional[ModelInfo] = Field(None, description="Info about the model")


class ModelInformation(BaseModel):
    """Information about a model"""

    modelfile: str = Field(..., description="The path to the model file")
    parameters: Optional[str] = Field(None, description="The parameters of the model")
    template: str = Field(..., description="The template of the model")
    details: ModelDetails = Field(..., description="Details about the model")
    model_info: ModelInfo = Field(..., description="Info about the model")


class ModelTagList(BaseModel):
    """A list of models"""

    models: list[ModelTag] = Field(..., description="The list of models")
