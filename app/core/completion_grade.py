"""Prescription completion grading, independent of persistence."""


def completion_grade(completed: int, total: int) -> tuple[float | None, str | None]:
    if total <= 0:
        return None, None
    completed = min(total, max(0, completed))
    percentage = completed / total * 100
    for threshold, grade in ((90, 'A'), (75, 'B'), (50, 'C')):
        if completed * 100 >= total * threshold:
            return percentage, grade
    return percentage, 'D'
