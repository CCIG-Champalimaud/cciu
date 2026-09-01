import SimpleITK as sitk
import numpy as np
from cciu.sitk_utils import resample_image_to_target
from scipy.spatial import distance


def filter_label_if_necessasry(mask: sitk.Image, label_idx: int | None):
    """
    Helper function to filter label values if `label_idx` is provided. Supports
    a single label index. If no label index is provided, the image is binarised
    (any value > 0 is set to 1).

    Args:
        mask (sitk.Image): SITK mask.
        label_idx (int): label index. Defaults to None.

    Returns:

    """
    if label_idx is None:
        return sitk.Cast(mask > 0, sitk.sitkUInt8)
    return sitk.Cast(mask == label_idx, sitk.sitkUInt8)


def compute_statistics_from_images(
    images: list[sitk.Image], label: sitk.Image
) -> dict:
    """
    Computes statistics from a set of images and a given mask.

    Args:
        images (list[sitk.Image]): List of images.
        label (sitk.Image): Mask.

    Returns:
        dict: Dictionary with statistics.
    """
    label_stats = sitk.LabelShapeStatisticsImageFilter()
    label_stats.Execute(label)
    unique_labels = label_stats.GetLabels()
    output_stats = []
    for image_idx, image in enumerate(images):
        resampled_label = sitk.Resample(
            label, image, sitk.Transform(), sitk.sitkLabelLinear, 0
        )
        stats = sitk.LabelIntensityStatisticsImageFilter()
        stats.Execute(resampled_label, image)
        for ul in unique_labels:
            output_stats.append(
                {
                    "Physical size (mm^3)": stats.GetPhysicalSize(ul),
                    "Principal axes (mm)": stats.GetPrincipalAxes(ul),
                    "Perimeter (mm)": stats.GetPerimeter(ul),
                    "Roundness": stats.GetRoundness(ul),
                    "Centroid (mm)": stats.GetCentroid(ul),
                    "Flatness": stats.GetFlatness(ul),
                    "Kurtosis": stats.GetKurtosis(ul),
                    "Mean intensity": stats.GetMean(ul),
                    "Median intensity": stats.GetMedian(ul),
                    "Minimum intensity": stats.GetMinimum(ul),
                    "Maximum intensity": stats.GetMaximum(ul),
                    "Skewness": stats.GetSkewness(ul),
                    "Intensity standard deviation": stats.GetStandardDeviation(
                        ul
                    ),
                    "Label": ul,
                    "Image index": image_idx,
                }
            )
    return output_stats


def erode_image(image: sitk.Image, radius: int = 2) -> sitk.Image:
    """
    Erodes an image by a given radius.

    Args:
        image (sitk.Image): Image to erode.
        radius (int, optional): Erosion radius in voxels. Defaults to 2.

    Returns:
        sitk.Image: Eroded image.
    """
    f = sitk.BinaryErodeImageFilter()
    f.SetKernelType(sitk.sitkBall)
    f.SetKernelRadius(radius)
    return sitk.Cast(f.Execute(image) > 0.5, image.GetPixelID())


def get_surface(image: sitk.Image) -> sitk.Image:
    """
    Gets the surface of an image.

    Args:
        image (sitk.Image): Image to get the surface of.

    Returns:
        sitk.Image: Surface of the image.
    """
    image = sitk.Cast(image, sitk.sitkInt16)
    eroded_image = erode_image(image, 1)
    return image - eroded_image


def calculate_distance_to_surface(
    mask_parent: sitk.Image,
    mask_child: sitk.Image,
    label_idx_parent: int | None = None,
    label_idx_child: int | None = None,
) -> sitk.Image:
    """
    Calculates the minimum distance from each voxel in the child image to the
    surface of the parent image.

    Args:
        mask_parent (sitk.Image): Parent image.
        mask_child (sitk.Image): Child image.
        label_idx_parent (int, optional): label for parent image.
        label_idx_child (int, optional): label for child image.

    Returns:
        sitk.Image: Minimum distance from each voxel in the child image to the
            surface of the parent image.
    """
    mask_child = resample_image_to_target(mask_child, mask_parent, is_mask=True)
    mask_parent = filter_label_if_necessasry(mask_parent, label_idx_parent)
    mask_child = filter_label_if_necessasry(mask_child, label_idx_child)
    surface_child = sitk.GetArrayFromImage(get_surface(mask_child))
    surface_parent = sitk.GetArrayFromImage(get_surface(mask_parent))
    sp = mask_child.GetSpacing()
    sp = np.array([sp[2], sp[0], sp[1]])[None]

    coords_child = np.stack(np.where(surface_child > 0), 1)
    coords_parent = np.stack(np.where(surface_parent > 0), 1)
    coords_child = coords_child * sp
    coords_parent = coords_parent * sp
    distances = distance.cdist(coords_child, coords_parent)
    distances = np.min(distances)
    return distances


def calculate_intersection(
    mask_1: sitk.Image,
    mask_2: sitk.Image,
    label_idx_1: int | None = None,
    label_idx_2: int | None = None,
) -> float:
    """
    Calculates the Jaccard index between two masks after filtering to specific
    label indices. If no label indices are provided, the all labels are
    considered.

    Args:
        mask_1 (sitk.Image): first SITK image.
        mask_2 (sitk.Image): second SITK image.
        label_idx_1 (int, optional): label index to filter labels in the first
            SITK image.
        label_idx_2 (int, optional): label index to filter labels in the second
            SITK image.
    """
    f = sitk.LabelOverlapMeasuresImageFilter()
    mask_2 = resample_image_to_target(mask_2, mask_1, is_mask=True)
    mask_1 = filter_label_if_necessasry(mask_1, label_idx_1)
    mask_2 = filter_label_if_necessasry(mask_2, label_idx_2)
    f.Execute(mask_1, mask_2)
    iou = f.GetJaccardCoefficient(1)
    return iou
