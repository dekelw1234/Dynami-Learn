import numpy as np


def get_el_centro_record():
    """
    Returns (times, accelerations_in_g) for El Centro 1940 (N-S component).
    Data is simplified for this project (captured peaks).
    """
    # [Time (s), Accel (g)]
    data = np.array([
        [0.00, 0.000], [0.50, 0.010], [1.00, 0.040], [1.40, -0.05],
        [1.80, -0.09], [2.00, 0.150], [2.14, 0.319], [2.40, -0.12],  # Peak ~0.32g
        [2.80, -0.25], [3.20, 0.180], [3.70, -0.15], [4.20, 0.120],
        [4.80, -0.10], [5.50, 0.060], [7.00, -0.04], [9.00, 0.020],
        [12.0, 0.000], [30.0, 0.000]
    ])

    t_points = data[:, 0]
    a_points_g = data[:, 1]  # in units of 'g'

    return t_points, a_points_g


def get_earthquake_force(t: float, M: np.ndarray, scaling_factor: float = 1.0) -> np.ndarray:
    """
    מחשב כוח אינרציה על כל הקומות:
    F(t) = - M * {1} * ag(t)
    """
    t_data, a_data_g = get_el_centro_record()

    # 1. מציאת התאוצה בזמן t (אינטרפולציה)
    # אם הזמן עבר את הרעידה, התאוצה היא 0
    if t > t_data[-1] or t < 0:
        ag_g = 0.0
    else:
        ag_g = np.interp(t, t_data, a_data_g)

    # המרה מ-g ל-m/s^2
    ag_ms2 = ag_g * 9.807 * scaling_factor

    # 2. וקטור השפעה (כל הקומות זזות ביחד אופקית)
    influence_vec = np.ones(M.shape[0])

    # 3. חישוב הכוח: F = -M * a
    # המינוס חשוב! כשהקרקע זזה ימינה, הבניין "מרגיש" כוח שמאלה.
    force_vec = -1.0 * (M @ influence_vec) * ag_ms2

    return force_vec