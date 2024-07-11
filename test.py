from pydantic import BaseModel


class TestModel(BaseModel):
    name: str


a = TestModel(name="test")

a = a.model_dump_json()

b = TestModel.model_validate_json(a)

print(b.name)
