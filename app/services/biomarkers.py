from __future__ import annotations
import math
from pathlib import Path
from typing import Any, Dict, Optional
import numpy as np
from PIL import Image
from skimage.morphology import skeletonize
from app.config import MAX_ROI_SIZE, OD_DIAMETER_UM
from app.infrastructure.model_loader import ModelBundle
from app.services.diameter_visualization import save_diameter_image


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        value = float(value)
    except Exception:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


def save_diameter_image(image: Image.Image, measurements, output_path: Path) -> bool:
    if not measurements:
        return False
    result = image.convert("RGBA")
    has_measurements = False
    for measurement in measurements:
        plot = measurement.get("plot")
        if plot is None:
            continue
        rgba = np.clip(np.nan_to_num(plot), 0, 1)
        if not np.any(rgba[..., 3]):
            continue
        overlay = Image.fromarray((rgba * 255).astype(np.uint8))
        result = Image.alpha_composite(result, overlay)
        has_measurements = True
    if has_measurements:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.convert("RGB").save(output_path, format="PNG")
    return has_measurements


def extract_features(
    models: ModelBundle, image_path: Path, artery_path: Path, vein_path: Path,
    *, diameter_paths: Optional[Dict[str, Path]] = None,
) -> Dict[str, Any]:
    if not all([models.segmenter, models.geometricalVBMs, models.creVBMs]):
        raise RuntimeError("Los módulos de PVBM no están cargados")

    image = Image.open(image_path).convert("RGB")
    segmentation = np.array(Image.open(artery_path)) / 255.0
    if segmentation.ndim == 3:
        segmentation = segmentation[..., 0]
    target_hw = segmentation.shape[:2]
    image = image.resize((target_hw[1], target_hw[0]), Image.BILINEAR)
    skeleton = skeletonize(segmentation > 0.5) * 1

    disc_seg_raw = np.array(models.segmenter.segment(image_path=str(image_path)))
    optic_disc_np = np.array(
        Image.fromarray(disc_seg_raw).resize((target_hw[1], target_hw[0]), Image.NEAREST)
    ).astype(np.uint8)
    optic_disc = Image.fromarray(optic_disc_np)

    center, radius, roi, zones_ABC = models.segmenter.post_processing(
        segmentation=optic_disc,
        max_roi_size=MAX_ROI_SIZE,
    )
    disc_diameter_px = 2 * radius
    um_per_px = OD_DIAMETER_UM / disc_diameter_px if disc_diameter_px > 0 else np.nan

    segmentation_roi, skeleton_roi = models.geometricalVBMs.apply_roi(
        segmentation=segmentation,
        skeleton=skeleton,
        zones_ABC=zones_ABC,
        roi=roi,
    )
    geom_vbms, _visual = models.geometricalVBMs.compute_geomVBMs(
        blood_vessel=segmentation_roi,
        skeleton=skeleton_roi,
        xc=center[0],
        yc=center[1],
        radius=radius,
    )
    area, TI, medTor, _ovlen, _medianba, _startp, _endp, _interp = geom_vbms

    seg_roi_cre, skel_roi_cre = models.creVBMs.apply_roi(
        segmentation=segmentation,
        skeleton=skeleton,
        zones_ABC=zones_ABC,
    )
    out_artery = models.creVBMs.compute_central_retinal_equivalents(
        blood_vessel=seg_roi_cre.copy(),
        skeleton=skel_roi_cre.copy(),
        xc=center[0],
        yc=center[1],
        radius=radius,
        artery=True,
        Toplot=bool(diameter_paths),
    )
    if out_artery == -1:
        craek = np.nan
    else:
        cre_art, plots_artery = out_artery
        craek = cre_art.get("craek", np.nan)
        if craek == -1:
            craek = np.nan
        if diameter_paths:
            save_diameter_image(
                image, plots_artery, diameter_paths["artery"],
                segmentation_roi=seg_roi_cre,
                zones_ABC=zones_ABC,
            )
        del plots_artery
    del out_artery

    seg_vein = np.array(Image.open(vein_path))
    if seg_vein.ndim == 3:
        seg_vein = seg_vein[..., 0]
    seg_vein = (seg_vein > 127).astype(np.uint8)
    skel_vein = skeletonize(seg_vein > 0) * 1
    seg_roi_v, skel_roi_v = models.creVBMs.apply_roi(
        segmentation=seg_vein,
        skeleton=skel_vein,
        zones_ABC=zones_ABC,
    )
    out_vein = models.creVBMs.compute_central_retinal_equivalents(
        blood_vessel=seg_roi_v.copy(),
        skeleton=skel_roi_v.copy(),
        xc=center[0],
        yc=center[1],
        radius=radius,
        artery=False,
        Toplot=bool(diameter_paths),
    )
    if out_vein == -1:
        crvek = np.nan
    else:
        cre_vein, plots_vein = out_vein
        crvek = cre_vein.get("crvek", np.nan)
        if crvek == -1:
            crvek = np.nan
        if diameter_paths:
            save_diameter_image(
                image, plots_vein, diameter_paths["vein"],
                segmentation_roi=seg_roi_v,
                zones_ABC=zones_ABC,
            )
        del plots_vein
    del out_vein

    craek_um = craek * um_per_px if np.isfinite(craek) and np.isfinite(um_per_px) else np.nan
    crvek_um = crvek * um_per_px if np.isfinite(crvek) and np.isfinite(um_per_px) else np.nan
    area_um2 = area * (um_per_px ** 2) if np.isfinite(um_per_px) else np.nan
    avr = craek / crvek if (np.isfinite(craek) and np.isfinite(crvek) and crvek > 0) else np.nan

    return {
        "imagen": image_path.stem,
        "craek": _safe_float(craek),
        "crvek": _safe_float(crvek),
        "craek_um": _safe_float(craek_um),
        "crvek_um": _safe_float(crvek_um),
        "avr_knudtson": _safe_float(avr),
        "area_px": _safe_float(area),
        "area_um2": _safe_float(area_um2),
        "TI": _safe_float(TI),
        "median_tortuosity": _safe_float(medTor),
        "disc_diameter_px": _safe_float(disc_diameter_px),
        "um_per_px": _safe_float(um_per_px),
    }
