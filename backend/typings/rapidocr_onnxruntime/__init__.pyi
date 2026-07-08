from typing import Any, List, Optional, Tuple, Union

class RapidOCR:
    def __init__(self, config_path: str | None = None, **kwargs: Any) -> None: ...
    def __call__(
        self,
        img_content: Union[str, bytes, Any],
        use_det: bool | None = None,
        use_cls: bool | None = None,
        use_rec: bool | None = None,
        **kwargs: Any,
    ) -> Tuple[Optional[List[List[Any]]], Optional[List[float]]]: ...

class LoadImageError(Exception): ...
class VisRes: ...
