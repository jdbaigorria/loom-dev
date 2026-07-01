from pydantic import BaseModel, Field


# Example output class
class PersonInfo(BaseModel):
    """Model that contains information about a Person"""

    name: str = Field(description="Name of the person")
    age: int = Field(description="Age of the person")
    occupation: str = Field(description="Occupation of the person")
