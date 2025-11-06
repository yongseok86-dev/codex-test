class GuardrailViolation(Exception):
    pass


def ensure_safe(sql: str) -> None:
    lowered = sql.lower()
    deny = ["delete ", "update ", "insert ", "drop ", "truncate "]
    if any(tok in lowered for tok in deny):
        raise GuardrailViolation("mutating queries are not allowed")
    if " select * " in f" {lowered} ":
        raise GuardrailViolation("SELECT * is not allowed")

