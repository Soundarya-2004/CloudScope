import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta

def predict_future_costs(dates: list, costs: list, days_to_predict: int = 30):
    """
    Predict future AWS costs using a simple Linear Regression model based on historical data.
    Ensures predictions are continuous from the present date.
    """
    if len(costs) < 2:
        # Not enough data to predict, return whatever we have
        return dates, costs, [None] * len(costs)

    # 1. Prepare historical data
    # X will be days since the first historical date
    X = np.array(range(len(costs))).reshape(-1, 1)
    y = np.array(costs)

    # 2. Fit model
    model = LinearRegression()
    model.fit(X, y)

    # 3. Predict for the next `days_to_predict` days
    # We want the prediction to start from the last historical point to maintain continuity
    # instead of potentially jumping.
    future_X = np.array(range(len(costs), len(costs) + days_to_predict)).reshape(-1, 1)
    predicted_values = model.predict(future_X).tolist()

    # Ensure no negative costs for a startup product
    predicted_values = [max(0.0, float(c)) for c in predicted_values]

    # 4. Generate combined timeline
    last_date_str = dates[-1]
    last_date = datetime.strptime(last_date_str, "%Y-%m-%d")

    all_dates = list(dates)
    for i in range(1, days_to_predict + 1):
        next_date = (last_date + timedelta(days=i)).strftime("%Y-%m-%d")
        all_dates.append(next_date)

    # 5. Align costs for visualization
    # Historical costs are valid for historical dates
    hist_padded = list(costs) + [None] * days_to_predict

    # Predicted costs start after historical period
    pred_values_padded = [None] * len(costs) + predicted_values

    return all_dates, hist_padded, pred_values_padded
