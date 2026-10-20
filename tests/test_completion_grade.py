import pytest
from app.core.completion_grade import completion_grade

@pytest.mark.parametrize('completed,total,expected',[
    (100,100,'A'),(90,100,'A'),(899,1000,'B'),(75,100,'B'),
    (749,1000,'C'),(50,100,'C'),(49,100,'D'),(0,0,None),
])
def test_grade_boundaries(completed,total,expected):
    assert completion_grade(completed,total)[1] == expected
