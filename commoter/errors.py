"""Control-flow exceptions used instead of Rails' `redirect_to` / `render 422`."""

from __future__ import annotations


class ValidationError(Exception):
    """Business-rule failure. `messages` reads like Rails' `errors.full_messages`."""

    def __init__(self, *messages: str) -> None:
        self.messages: list[str] = [m for m in messages if m]
        super().__init__("; ".join(self.messages))


class RedirectError(Exception):
    """Raise from a dependency to bounce the request elsewhere."""

    def __init__(self, location: str, alert: str | None = None) -> None:
        self.location = location
        self.alert = alert
        super().__init__(location)


class NotFoundError(Exception):
    pass
