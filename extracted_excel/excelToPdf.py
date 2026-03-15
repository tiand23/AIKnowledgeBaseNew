from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, replace, fields, is_dataclass
from enum import Enum
from functools import partial, singledispatch
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    Generic,
    List,
    Optional,
    Protocol,
    Tuple,
    TypeVar,
    cast,
    Literal,
    runtime_checkable,
)

import numpy as np

try:
    import fitz
except ImportError:
    try:
        import pymupdf as fitz
    except ImportError:
        fitz = None

try:
    import win32com.client as win32
except ImportError:
    win32 = None

StageName = Literal["export", "crop", "finalize", "cleanup"]
StageOrder = Tuple[StageName, ...]

DEFAULT_STAGE_ORDER: Final[StageOrder] = ("export", "crop", "finalize", "cleanup")

EXPORTER_AUTO: Final[str] = "exporter.auto"
EXPORTER_EXCEL_WIN32: Final[str] = "excel.win32.export_one_page_per_sheet"
EXPORTER_LIBREOFFICE_OPENPYXL: Final[str] = "libreoffice.openpyxl.export_one_page_per_sheet"
CROPPER_PYMUPDF_BBOX: Final[str] = "pymupdf.crop_by_bbox"
FINALIZER_DEFAULT: Final[str] = "finalize.default"
CLEANUP_TEMP_MIDDLE_PDF: Final[str] = "cleanup.temp_middle_pdf"
DEFAULT_LIBREOFFICE_WINDOWS_PATH: Final[str] = r"C:\Program Files\LibreOffice\program\soffice.exe"
CONVERT_TIMEOUT_SECONDS: Final[int] = 180


class ArtifactKey(str, Enum):
    XLSX_ABS = "xlsx_abs"
    TEMP_MIDDLE_PDF = "temp_middle_pdf"
    MIDDLE_PDF = "middle_pdf"
    ENHANCED_PDF = "enhanced_pdf"
    EXPORTED_PDF = "exported_pdf"


TArtifact = TypeVar("TArtifact")


@dataclass(frozen=True, slots=True)
class Artifact(Generic[TArtifact]):

    key: ArtifactKey
    value: TArtifact


class ArtifactBag:

    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store: Dict[ArtifactKey, Artifact[Any]] = {}

    def put(self, key: ArtifactKey, value: Any) -> None:
        self._store[key] = Artifact(key=key, value=value)

    def get(self, key: ArtifactKey, default: Any = None) -> Any:
        a = self._store.get(key)
        return a.value if a is not None else default

    def __setitem__(self, key: ArtifactKey, value: Any) -> None:
        self.put(key, value)

    def __getitem__(self, key: ArtifactKey) -> Any:
        a = self._store.get(key)
        if a is None:
            raise KeyError(key)
        return a.value

    def __contains__(self, key: ArtifactKey) -> bool:
        return key in self._store


@dataclass(frozen=True, slots=True)
class CropConfig:

    white_thresh: int
    margin_ratio: float
    bbox_dpi: int

    def __post_init__(self) -> None:
        if not (0 <= self.white_thresh <= 255):
            raise ValueError("error: white_thresh")
        if not (0.0 <= self.margin_ratio <= 1.0):
            raise ValueError("error: margin_ratio")
        if self.bbox_dpi < 72 or self.bbox_dpi > 600:
            raise ValueError("error: bbox_dpi")


@dataclass(frozen=True, slots=True)
class PathConfig:

    input_xlsx: str


@dataclass(frozen=True, slots=True)
class RuntimeConfig:

    output_middle_pdf: bool = False
    exporter_key: str = EXPORTER_AUTO
    cropper_key: str = CROPPER_PYMUPDF_BBOX
    finalize_key: str = FINALIZER_DEFAULT
    cleanup_key: str = CLEANUP_TEMP_MIDDLE_PDF
    env_prefix: str = "TOPDF_"


@dataclass(frozen=True, slots=True)
class AppConfig:

    paths: PathConfig
    crop: CropConfig
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    @classmethod
    def default(cls) -> "AppConfig":
        return cls(
            paths=PathConfig(input_xlsx="input.xlsx"),
            crop=CropConfig(
                white_thresh=250,
                margin_ratio=0.02,
                bbox_dpi=150,
            ),
            runtime=RuntimeConfig(output_middle_pdf=False),
        )


TConfig = TypeVar("TConfig", bound=AppConfig)


def _dataclass_deep_merge(base: Any, override: Any) -> Any:
    if override is None:
        return base
    if is_dataclass(base) and is_dataclass(override) and type(base) is type(override):
        updates: Dict[str, Any] = {}
        for f in fields(base):
            b_val = getattr(base, f.name)
            o_val = getattr(override, f.name)
            updates[f.name] = _dataclass_deep_merge(b_val, o_val)
        return replace(base, **updates)
    return override


def merge_config(base: AppConfig, override: Optional[AppConfig]) -> AppConfig:
    if override is None:
        return base
    merged = _dataclass_deep_merge(base, override)
    if not isinstance(merged, AppConfig):
        raise TypeError("error: merge_config")
    return merged


def validate_config(config: AppConfig) -> None:
    if not config.paths.input_xlsx or not config.paths.input_xlsx.strip():
        raise ValueError("error: input_xlsx")
    if not os.path.isfile(config.paths.input_xlsx):
        raise FileNotFoundError(f"error: {config.paths.input_xlsx}")


def _normalize_path(path_value: str) -> str:
    return os.path.abspath(os.path.expandvars(os.path.expanduser(path_value.strip())))


def _parse_env_int(var_name: str, raw: Optional[str], default: int) -> int:
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise ToPdfError(f"error: {var_name}") from exc


def _parse_env_float(var_name: str, raw: Optional[str], default: float) -> float:
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ToPdfError(f"error: {var_name}") from exc


def _parse_env_bool(var_name: str, raw: Optional[str], default: bool) -> bool:
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "y", "on"}:
        return True
    if value in {"0", "false", "no", "n", "off"}:
        return False
    raise ToPdfError(f"error: {var_name}")


class ToPdfError(Exception):

    def __init__(self, message: str = "", *, cause: Optional[BaseException] = None) -> None:
        self.message = message
        self.cause = cause
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause

    def __str__(self) -> str:
        if self.cause is not None and self.message:
            return f"{self.message}\nerror: {self.cause}"
        if self.message:
            return self.message
        return self.__class__.__name__


class DependencyError(ToPdfError):

    def __init__(self, message: str = "error: dependency missing", *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, cause=cause)


class ExportError(ToPdfError):

    def __init__(self, message: str = "error: excel export pdf failed", *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, cause=cause)


class CropError(ToPdfError):

    def __init__(self, message: str = "error: pdf crop failed", *, cause: Optional[BaseException] = None) -> None:
        super().__init__(message, cause=cause)


def ensure_fitz_available() -> None:
    if fitz is None:
        raise DependencyError("error: pymupdf not available")


def ensure_win32_available() -> None:
    if win32 is None:
        raise DependencyError("error: pywin32 not available")


def ensure_openpyxl_available() -> None:
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:
        raise DependencyError("error: openpyxl not available") from exc


def _is_windows_runtime() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")


def _resolve_libreoffice_command() -> str:
    env_path = os.environ.get("SOFFICE_PATH", "").strip()
    if env_path and os.path.isfile(env_path):
        return env_path

    if _is_windows_runtime() and os.path.isfile(DEFAULT_LIBREOFFICE_WINDOWS_PATH):
        return DEFAULT_LIBREOFFICE_WINDOWS_PATH

    for cmd in ("libreoffice", "soffice"):
        resolved = shutil.which(cmd)
        if resolved:
            return resolved
    raise DependencyError("error: libreoffice/soffice not available")


@singledispatch
def resolve_xlsx_absolute(xlsx_like: Any) -> str:
    raise TypeError(f"error: unsupported xlsx input type: {type(xlsx_like)}")


@resolve_xlsx_absolute.register
def _(xlsx_path: str) -> str:
    return _normalize_path(xlsx_path)


@resolve_xlsx_absolute.register
def _(paths: PathConfig) -> str:
    return _normalize_path(paths.input_xlsx)


def pdf_path_from_xlsx(xlsx_abs: str) -> str:
    base, _ = os.path.splitext(xlsx_abs)
    return base + ".pdf"


def middle_pdf_path_from_xlsx(xlsx_abs: str) -> str:
    base, _ = os.path.splitext(xlsx_abs)
    return base + "_middle.pdf"


def enhanced_pdf_path_from_xlsx(xlsx_abs: str) -> str:
    base, _ = os.path.splitext(xlsx_abs)
    return base + "_enhanced.pdf"


def cropped_pdf_path_from_pdf(pdf_path: str) -> str:
    base, _ = os.path.splitext(pdf_path)
    return base + "_cropped.pdf"


def build_temp_middle_pdf_path(xlsx_abs: str) -> str:
    out_dir = os.path.dirname(xlsx_abs)
    base_name = os.path.splitext(os.path.basename(xlsx_abs))[0]
    with tempfile.NamedTemporaryFile(
        prefix=f"{base_name}_tmp_",
        suffix=".pdf",
        dir=out_dir,
        delete=False,
    ) as f:
        temp_path = f.name
    return temp_path


def assert_nonempty_file(path: str, stage_name: str) -> None:
    if not os.path.isfile(path):
        raise ToPdfError(f"error: {stage_name} failed: file not found {path}")
    if os.path.getsize(path) <= 0:
        raise ToPdfError(f"error: {stage_name} failed: file is empty {path}")


@dataclass(slots=True)
class PipelineContext(Generic[TConfig]):
    cfg: TConfig
    artifacts: ArtifactBag = field(default_factory=ArtifactBag)
    events: List[StageName] = field(default_factory=list)


ContractPredicate = Callable[[PipelineContext[AppConfig]], None]


def _predicate_stage_order(required_order: Tuple[StageName, ...]) -> ContractPredicate:

    def _check(ctx: PipelineContext[AppConfig]) -> None:
        events = ctx.events
        prefix = required_order[: len(events)]
        if tuple(events) != prefix:
            raise ToPdfError(f"error: stage order violation: {events} != {list(prefix)}")

    return _check


def _predicate_enhanced_pdf_nonempty(ctx: PipelineContext[AppConfig]) -> None:
    enhanced = ctx.artifacts.get(ArtifactKey.ENHANCED_PDF)
    if not enhanced:
        raise ToPdfError("error: enhanced_pdf")
    assert_nonempty_file(enhanced, "finalize")


def _noop_predicate(_ctx: PipelineContext[AppConfig]) -> None:
    pass


def _compose_predicates(*predicates: ContractPredicate) -> ContractPredicate:

    def _combined(ctx: PipelineContext[AppConfig]) -> None:
        for p in predicates:
            p(ctx)

    return _combined


@dataclass(frozen=True, slots=True)
class Contract:

    _run: ContractPredicate = field(default=_noop_predicate)
    _required_stage_order: StageOrder = DEFAULT_STAGE_ORDER

    @classmethod
    def baseline(cls, required_stage_order: StageOrder = DEFAULT_STAGE_ORDER) -> "Contract":
        run = _compose_predicates(
            _predicate_stage_order(required_stage_order),
            _predicate_enhanced_pdf_nonempty,
        )
        return cls(_run=run, _required_stage_order=required_stage_order)

    def and_then(self, other: "Contract") -> "Contract":
        return Contract(
            _run=_compose_predicates(self._run, other._run),
            _required_stage_order=self._required_stage_order,
        )

    def assert_stage_order_prefix(self, events: List[StageName]) -> None:
        dummy = PipelineContext(cfg=AppConfig.default())
        dummy.events = list(events)
        _predicate_stage_order(self._required_stage_order)(dummy)

    def assert_artifacts(self, ctx: PipelineContext[AppConfig]) -> None:
        self._run(ctx)


Ctx = TypeVar("Ctx", bound=PipelineContext[Any])


@runtime_checkable
class Stage(Protocol[Ctx]):
    name: StageName

    def __call__(self, ctx: Ctx) -> Ctx: ...


StageFactory = Callable[[AppConfig], Stage[PipelineContext[AppConfig]]]


@dataclass(slots=True)
class StageRegistry:
    factories: Dict[str, StageFactory] = field(default_factory=dict)

    def register(self, key: str, factory: StageFactory) -> None:
        self.factories[key] = factory

    def resolve(self, key: str, cfg: AppConfig) -> Stage[PipelineContext[AppConfig]]:
        if key not in self.factories:
            raise ToPdfError(f"error: unknown strategy key: {key}")
        return self.factories[key](cfg)


_STAGE_REGISTRY: StageRegistry = StageRegistry()


def register(key: str) -> Callable[[StageFactory], StageFactory]:

    def _deco(fn: StageFactory) -> StageFactory:
        _STAGE_REGISTRY.register(key, fn)
        return fn

    return _deco


def compose_stages(*stages: Stage[Ctx]) -> Stage[Ctx]:

    class _Composed(Stage[Ctx]):  # type: ignore[misc]
        name: StageName = "finalize"

        def __call__(self, ctx: Ctx) -> Ctx:
            for s in stages:
                ctx = s(ctx)
            return ctx

    return _Composed()


def with_observability(
    stage: Stage[PipelineContext[AppConfig]],
    *,
    logger: logging.Logger,
    contract: Contract,
) -> Stage[PipelineContext[AppConfig]]:

    class _Wrapped(Stage[PipelineContext[AppConfig]]):  # type: ignore[misc]
        name: StageName = stage.name

        def __call__(self, ctx: PipelineContext[AppConfig]) -> PipelineContext[AppConfig]:
            ctx.events.append(stage.name)
            contract.assert_stage_order_prefix(ctx.events)
            t0 = time.perf_counter()
            try:
                out_ctx = stage(ctx)
                return out_ctx
            except Exception as e:
                raise ToPdfError(f"error: stage {stage.name} failed", cause=e)
            finally:
                elapsed = time.perf_counter() - t0
                logger.info("stage %s done in %.3fs", stage.name, elapsed)

    return _Wrapped()


def _apply_page_setup_fit_to_one_page(workbook: object) -> None:
    for ws in workbook.Worksheets:
        ps = ws.PageSetup
        ps.Zoom = False
        ps.FitToPagesWide = 1
        ps.FitToPagesTall = 1


def _export_workbook_to_pdf(workbook: object, out_pdf: str) -> None:
    xl_type_pdf = 0
    workbook.ExportAsFixedFormat(Type=xl_type_pdf, Filename=out_pdf)


def export_excel_to_pdf_one_page_per_sheet(xlsx_path: str, output_pdf: Optional[str] = None) -> str:
    if not os.path.isfile(xlsx_path):
        raise FileNotFoundError(f"error: {xlsx_path}")

    xlsx_abs = resolve_xlsx_absolute(xlsx_path)
    out_pdf = os.path.abspath(output_pdf) if output_pdf else pdf_path_from_xlsx(xlsx_abs)

    excel = None
    workbook = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        workbook = excel.Workbooks.Open(xlsx_abs)
        _apply_page_setup_fit_to_one_page(workbook)
        _export_workbook_to_pdf(workbook, out_pdf)
        return out_pdf
    except Exception as e:
        raise ExportError(f"error: excel export pdf failed: {e}") from e
    finally:
        if workbook is not None:
            try:
                workbook.Close(SaveChanges=False)
            except Exception:
                pass
        if excel is not None:
            try:
                excel.Quit()
            except Exception:
                pass


def export_excel_to_pdf_one_page_per_sheet_via_libreoffice(
    xlsx_path: str,
    output_pdf: Optional[str] = None,
) -> str:
    ensure_openpyxl_available()
    lo_cmd = _resolve_libreoffice_command()

    from openpyxl import load_workbook
    from openpyxl.worksheet.properties import PageSetupProperties

    if not os.path.isfile(xlsx_path):
        raise FileNotFoundError(f"error: {xlsx_path}")

    xlsx_abs = resolve_xlsx_absolute(xlsx_path)
    out_pdf = os.path.abspath(output_pdf) if output_pdf else pdf_path_from_xlsx(xlsx_abs)

    with tempfile.TemporaryDirectory(prefix="xlsx2pdf_") as tmpdir:
        tmp_xlsx = os.path.join(tmpdir, os.path.basename(xlsx_abs))
        _, ext = os.path.splitext(xlsx_abs)
        keep_vba = ext.lower() == ".xlsm"

        wb = None
        try:
            wb = load_workbook(xlsx_abs, keep_vba=keep_vba)
            for ws in wb.worksheets:
                ws.page_setup.scale = None
                ws.page_setup.fitToWidth = 1
                ws.page_setup.fitToHeight = 1
                if ws.sheet_properties.pageSetUpPr is None:
                    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
                else:
                    ws.sheet_properties.pageSetUpPr.fitToPage = True
            wb.save(tmp_xlsx)
        finally:
            if wb is not None:
                wb.close()

        out_dir = os.path.dirname(out_pdf) or "."
        cmd = [lo_cmd, "--headless", "--convert-to", "pdf", "--outdir", out_dir, tmp_xlsx]
        generated_pdf = os.path.join(
            out_dir,
            os.path.splitext(os.path.basename(tmp_xlsx))[0] + ".pdf",
        )
        try:
            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=CONVERT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise ExportError(
                f"error: libreoffice convert timeout after {CONVERT_TIMEOUT_SECONDS}s"
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            detail = stderr or stdout or "unknown error"
            raise ExportError(f"error: libreoffice convert failed: {detail}") from exc

        if not os.path.isfile(generated_pdf):
            raise ExportError(f"error: pdf not generated: {generated_pdf}")

        if os.path.abspath(generated_pdf) != os.path.abspath(out_pdf):
            if os.path.isfile(out_pdf):
                os.remove(out_pdf)
            shutil.move(generated_pdf, out_pdf)

    assert_nonempty_file(out_pdf, "export")
    return out_pdf


def _pixmap_to_gray_array(pix: object) -> np.ndarray:
    h, w = pix.height, pix.width
    n = pix.n
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(h, w, n)
    if n >= 3:
        gray = arr.max(axis=2)
    else:
        gray = arr.squeeze()
    return gray


def _content_mask(gray: np.ndarray, white_thresh: int) -> Tuple[np.ndarray, np.ndarray]:
    nonwhite = gray < white_thresh
    rows = nonwhite.any(axis=1)
    cols = nonwhite.any(axis=0)
    return rows, cols


def _pixel_bounds_from_mask(
    rows: np.ndarray, cols: np.ndarray, height: int, width: int
) -> Tuple[int, int, int, int]:
    if not rows.any() or not cols.any():
        return 0, 0, width, height
    y0 = int(np.argmax(rows))
    y1 = int(height - 1 - np.argmax(rows[::-1]))
    x0 = int(np.argmax(cols))
    x1 = int(width - 1 - np.argmax(cols[::-1]))
    return x0, y0, x1, y1


def _apply_margin_pixels(
    x0: int, y0: int, x1: int, y1: int,
    width: int, height: int, margin_ratio: float
) -> Tuple[int, int, int, int]:
    mw = max(1, int(width * margin_ratio))
    mh = max(1, int(height * margin_ratio))
    x0 = max(0, x0 - mw)
    y0 = max(0, y0 - mh)
    x1 = min(width, x1 + mw)
    y1 = min(height, y1 + mh)
    return x0, y0, x1, y1


def content_bbox_from_pixmap(
    pix: object,
    white_thresh: int = 250,
    margin_ratio: float = 0.02,
) -> Tuple[int, int, int, int]:
    h, w = pix.height, pix.width
    gray = _pixmap_to_gray_array(pix)
    rows, cols = _content_mask(gray, white_thresh)
    x0, y0, x1, y1 = _pixel_bounds_from_mask(rows, cols, h, w)
    x0, y0, x1, y1 = _apply_margin_pixels(x0, y0, x1, y1, w, h, margin_ratio)
    return x0, y0, x1, y1


def pixel_bbox_to_pdf_rect(
    px0: int, py0: int, px1: int, py1: int,
    page_rect: object, pix_w: int, pix_h: int
) -> object:
    sx = page_rect.width / pix_w
    sy = page_rect.height / pix_h
    return fitz.Rect(
        page_rect.x0 + px0 * sx,
        page_rect.y0 + py0 * sy,
        page_rect.x0 + px1 * sx,
        page_rect.y0 + py1 * sy,
    )


def crop_pdf_pages(
    input_pdf: str,
    output_pdf: str,
    config: CropConfig,
) -> None:
    ensure_fitz_available()
    if not os.path.isfile(input_pdf):
        raise FileNotFoundError(f"error: {input_pdf}")

    doc = fitz.open(input_pdf)
    out = fitz.open()

    try:
        for i in range(len(doc)):
            page = doc[i]
            rect = page.rect
            pix = page.get_pixmap(dpi=config.bbox_dpi)
            px0, py0, px1, py1 = content_bbox_from_pixmap(
                pix,
                white_thresh=config.white_thresh,
                margin_ratio=config.margin_ratio,
            )
            crop_rect = pixel_bbox_to_pdf_rect(
                px0, py0, px1, py1, rect, pix.width, pix.height
            )
            page.set_cropbox(crop_rect)
            out.insert_pdf(doc, from_page=i, to_page=i)

        out.save(output_pdf, deflate=True)
    except Exception as e:
        raise CropError(f"error: pdf crop failed: {e}") from e
    finally:
        out.close()
        doc.close()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )


def setup_logging_with_level(log_level: str = "INFO") -> None:
    level_name = log_level.strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(message)s",
    )


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Excel workbook to a cropped PDF.",
    )
    parser.add_argument(
        "--input",
        dest="input_xlsx",
        help="Path to input xlsx file. Defaults to input.xlsx.",
    )
    parser.add_argument(
        "--white-thresh",
        dest="white_thresh",
        type=int,
        help="White threshold for content detection. Range: 0-255.",
    )
    parser.add_argument(
        "--margin-ratio",
        dest="margin_ratio",
        type=float,
        help="Margin ratio around detected content. Range: 0.0-1.0.",
    )
    parser.add_argument(
        "--bbox-dpi",
        dest="bbox_dpi",
        type=int,
        help="DPI used to rasterize PDF page before bbox detection. Range: 72-600.",
    )
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
        help="Logging level. Defaults to INFO.",
    )
    parser.add_argument(
        "--exporter",
        dest="exporter_key",
        choices=(EXPORTER_AUTO, EXPORTER_EXCEL_WIN32, EXPORTER_LIBREOFFICE_OPENPYXL),
        help="Exporter strategy. Defaults to exporter.auto.",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--output-middle-pdf",
        dest="output_middle_pdf",
        action="store_true",
        help="Keep exported middle PDF alongside final enhanced PDF.",
    )
    output_group.add_argument(
        "--no-output-middle-pdf",
        dest="output_middle_pdf",
        action="store_false",
        help="Do not keep middle PDF.",
    )
    parser.set_defaults(output_middle_pdf=None)
    return parser


def _apply_cli_overrides(base_cfg: AppConfig, args: argparse.Namespace) -> AppConfig:
    cfg = base_cfg
    if args.input_xlsx is not None:
        raw_path = args.input_xlsx.strip()
        if not raw_path:
            raise ToPdfError("error: --input")
        normalized_input_xlsx = _normalize_path(raw_path)
        cfg = replace(cfg, paths=replace(cfg.paths, input_xlsx=normalized_input_xlsx))
    if args.white_thresh is not None:
        cfg = replace(
            cfg,
            crop=replace(cfg.crop, white_thresh=args.white_thresh),
        )
    if args.margin_ratio is not None:
        cfg = replace(
            cfg,
            crop=replace(cfg.crop, margin_ratio=args.margin_ratio),
        )
    if args.bbox_dpi is not None:
        cfg = replace(
            cfg,
            crop=replace(cfg.crop, bbox_dpi=args.bbox_dpi),
        )
    if args.exporter_key is not None:
        cfg = replace(
            cfg,
            runtime=replace(cfg.runtime, exporter_key=args.exporter_key),
        )
    return cfg


@register(EXPORTER_AUTO)
def _auto_export_factory(cfg: AppConfig) -> Stage[PipelineContext[AppConfig]]:
    chosen_key = EXPORTER_EXCEL_WIN32 if _is_windows_runtime() and win32 is not None else EXPORTER_LIBREOFFICE_OPENPYXL
    return _STAGE_REGISTRY.resolve(chosen_key, replace(cfg, runtime=replace(cfg.runtime, exporter_key=chosen_key)))


@register(EXPORTER_EXCEL_WIN32)
def _export_factory(cfg: AppConfig) -> Stage[PipelineContext[AppConfig]]:
    class _Export(Stage[PipelineContext[AppConfig]]):  # type: ignore[misc]
        name: StageName = "export"

        def __call__(self, ctx: PipelineContext[AppConfig]) -> PipelineContext[AppConfig]:
            xlsx_abs = resolve_xlsx_absolute(ctx.cfg.paths)
            temp_middle_pdf_path = build_temp_middle_pdf_path(xlsx_abs)
            ctx.artifacts[ArtifactKey.XLSX_ABS] = xlsx_abs
            ctx.artifacts[ArtifactKey.TEMP_MIDDLE_PDF] = temp_middle_pdf_path

            pdf_path = export_excel_to_pdf_one_page_per_sheet(
                ctx.cfg.paths.input_xlsx, output_pdf=temp_middle_pdf_path
            )
            assert_nonempty_file(pdf_path, "export")
            ctx.artifacts[ArtifactKey.EXPORTED_PDF] = pdf_path
            return ctx

    return _Export()


@register(EXPORTER_LIBREOFFICE_OPENPYXL)
def _export_libreoffice_factory(cfg: AppConfig) -> Stage[PipelineContext[AppConfig]]:
    class _ExportLibreOffice(Stage[PipelineContext[AppConfig]]):  # type: ignore[misc]
        name: StageName = "export"

        def __call__(self, ctx: PipelineContext[AppConfig]) -> PipelineContext[AppConfig]:
            xlsx_abs = resolve_xlsx_absolute(ctx.cfg.paths)
            temp_middle_pdf_path = build_temp_middle_pdf_path(xlsx_abs)
            ctx.artifacts[ArtifactKey.XLSX_ABS] = xlsx_abs
            ctx.artifacts[ArtifactKey.TEMP_MIDDLE_PDF] = temp_middle_pdf_path

            pdf_path = export_excel_to_pdf_one_page_per_sheet_via_libreoffice(
                ctx.cfg.paths.input_xlsx,
                output_pdf=temp_middle_pdf_path,
            )
            assert_nonempty_file(pdf_path, "export")
            ctx.artifacts[ArtifactKey.EXPORTED_PDF] = pdf_path
            return ctx

    return _ExportLibreOffice()


@register(CROPPER_PYMUPDF_BBOX)
def _crop_factory(cfg: AppConfig) -> Stage[PipelineContext[AppConfig]]:
    cropper = partial(crop_pdf_pages, config=cfg.crop)

    class _Crop(Stage[PipelineContext[AppConfig]]):  # type: ignore[misc]
        name: StageName = "crop"

        def __call__(self, ctx: PipelineContext[AppConfig]) -> PipelineContext[AppConfig]:
            xlsx_abs = cast(str, ctx.artifacts[ArtifactKey.XLSX_ABS])
            enhanced_pdf_path = enhanced_pdf_path_from_xlsx(xlsx_abs)
            exported_pdf = cast(str, ctx.artifacts[ArtifactKey.EXPORTED_PDF])
            cropper(exported_pdf, enhanced_pdf_path)
            assert_nonempty_file(enhanced_pdf_path, "crop")
            ctx.artifacts[ArtifactKey.ENHANCED_PDF] = enhanced_pdf_path
            return ctx

    return _Crop()


@register(FINALIZER_DEFAULT)
def _finalize_factory(cfg: AppConfig) -> Stage[PipelineContext[AppConfig]]:
    class _Finalize(Stage[PipelineContext[AppConfig]]):  # type: ignore[misc]
        name: StageName = "finalize"

        def __call__(self, ctx: PipelineContext[AppConfig]) -> PipelineContext[AppConfig]:
            if not cfg.runtime.output_middle_pdf:
                return ctx
            xlsx_abs = cast(str, ctx.artifacts[ArtifactKey.XLSX_ABS])
            middle_pdf_path = middle_pdf_path_from_xlsx(xlsx_abs)
            temp_middle_pdf_path = cast(str, ctx.artifacts.get(ArtifactKey.TEMP_MIDDLE_PDF, ""))
            if os.path.exists(middle_pdf_path):
                os.remove(middle_pdf_path)
            if temp_middle_pdf_path:
                os.replace(temp_middle_pdf_path, middle_pdf_path)
                ctx.artifacts[ArtifactKey.MIDDLE_PDF] = middle_pdf_path
                ctx.artifacts[ArtifactKey.TEMP_MIDDLE_PDF] = ""
            return ctx

    return _Finalize()


@register(CLEANUP_TEMP_MIDDLE_PDF)
def _cleanup_factory(cfg: AppConfig) -> Stage[PipelineContext[AppConfig]]:
    class _Cleanup(Stage[PipelineContext[AppConfig]]):  # type: ignore[misc]
        name: StageName = "cleanup"

        def __call__(self, ctx: PipelineContext[AppConfig]) -> PipelineContext[AppConfig]:
            temp_middle_pdf_path = cast(str, ctx.artifacts.get(ArtifactKey.TEMP_MIDDLE_PDF, ""))
            if temp_middle_pdf_path and os.path.exists(temp_middle_pdf_path):
                try:
                    os.remove(temp_middle_pdf_path)
                except Exception:
                    pass
            return ctx

    return _Cleanup()


def _default_registry() -> StageRegistry:
    return _STAGE_REGISTRY


def _load_env_override(prefix: str) -> Optional[AppConfig]:
    def _get(name: str) -> Optional[str]:
        return os.getenv(prefix + name)

    env_input_xlsx = _get("INPUT_XLSX")
    env_output_middle_pdf = _get("OUTPUT_MIDDLE_PDF")
    env_exporter_key = _get("EXPORTER_KEY")
    env_white_thresh = _get("WHITE_THRESH")
    env_margin_ratio = _get("MARGIN_RATIO")
    env_bbox_dpi = _get("BBOX_DPI")
    if (
        env_input_xlsx is None
        and env_output_middle_pdf is None
        and env_exporter_key is None
        and env_white_thresh is None
        and env_margin_ratio is None
        and env_bbox_dpi is None
    ):
        return None

    base = AppConfig.default()
    input_xlsx = base.paths.input_xlsx
    if env_input_xlsx is not None:
        if not env_input_xlsx.strip():
            raise ToPdfError(f"error: {prefix}INPUT_XLSX")
        input_xlsx = _normalize_path(env_input_xlsx)

    override = AppConfig(
        paths=PathConfig(input_xlsx=input_xlsx),
        crop=CropConfig(
            white_thresh=_parse_env_int(f"{prefix}WHITE_THRESH", env_white_thresh, base.crop.white_thresh),
            margin_ratio=_parse_env_float(f"{prefix}MARGIN_RATIO", env_margin_ratio, base.crop.margin_ratio),
            bbox_dpi=_parse_env_int(f"{prefix}BBOX_DPI", env_bbox_dpi, base.crop.bbox_dpi),
        ),
        runtime=replace(
            base.runtime,
            exporter_key=(env_exporter_key.strip() if env_exporter_key and env_exporter_key.strip() else base.runtime.exporter_key),
            output_middle_pdf=_parse_env_bool(
                f"{prefix}OUTPUT_MIDDLE_PDF",
                env_output_middle_pdf,
                base.runtime.output_middle_pdf,
            ),
        ),
    )
    return override


def run_pipeline(config: AppConfig, output_middle_pdf: Optional[bool] = None) -> str:
    logger = logging.getLogger(__name__)

    # Runtime override is applied only when env vars are explicitly provided.
    env_override = _load_env_override(config.runtime.env_prefix)
    merged_cfg = merge_config(config, env_override)
    if output_middle_pdf is not None:
        merged_cfg = replace(
            merged_cfg,
            runtime=replace(merged_cfg.runtime, output_middle_pdf=output_middle_pdf),
        )

    validate_config(merged_cfg)
    ensure_fitz_available()

    ctx = PipelineContext(cfg=merged_cfg)
    contract = Contract.baseline()
    registry = _default_registry()

    export_stage = with_observability(
        registry.resolve(merged_cfg.runtime.exporter_key, merged_cfg),
        logger=logger,
        contract=contract,
    )
    crop_stage = with_observability(
        registry.resolve(merged_cfg.runtime.cropper_key, merged_cfg),
        logger=logger,
        contract=contract,
    )
    finalize_stage = with_observability(
        registry.resolve(merged_cfg.runtime.finalize_key, merged_cfg),
        logger=logger,
        contract=contract,
    )
    cleanup_stage = with_observability(
        registry.resolve(merged_cfg.runtime.cleanup_key, merged_cfg),
        logger=logger,
        contract=contract,
    )

    try:
        logger.info("start excel export pdf...")
        ctx = export_stage(ctx)
        logger.info("excel export pdf completed: %s", ctx.artifacts[ArtifactKey.EXPORTED_PDF])

        logger.info("start pdf crop...")
        ctx = crop_stage(ctx)
        logger.info("enhanced pdf output: %s", ctx.artifacts[ArtifactKey.ENHANCED_PDF])

        ctx = finalize_stage(ctx)
        if merged_cfg.runtime.output_middle_pdf and ArtifactKey.MIDDLE_PDF in ctx.artifacts:
            logger.info("middle pdf output: %s", ctx.artifacts[ArtifactKey.MIDDLE_PDF])
    finally:
        try:
            if "finalize" in ctx.events:
                ctx = cleanup_stage(ctx)
            else:
                # Failure path may not satisfy stage-order contract; run raw cleanup instead.
                raw_cleanup_stage = registry.resolve(merged_cfg.runtime.cleanup_key, merged_cfg)
                ctx = raw_cleanup_stage(ctx)
        except Exception:
            logger.exception("error: cleanup stage failed")

    contract.assert_artifacts(ctx)
    return ctx.artifacts[ArtifactKey.ENHANCED_PDF]


def main(
    output_middle_pdf: Optional[bool] = None,
    argv: Optional[List[str]] = None,
) -> None:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    setup_logging_with_level(args.log_level)

    config = AppConfig.default()
    config = _apply_cli_overrides(config, args)

    effective_output_middle_pdf = (
        output_middle_pdf if output_middle_pdf is not None else args.output_middle_pdf
    )
    run_pipeline(config, output_middle_pdf=effective_output_middle_pdf)


if __name__ == "__main__":
    main()
