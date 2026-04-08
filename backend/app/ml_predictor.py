import numpy as np
from sklearn.linear_model import LinearRegression
from datetime import datetime, timedelta

def predict_future_costs(dates: list[str], costs: list[float], days_to_predict: int = 30):
    """
    Predict future AWS costs using a simple Linear Regression model based on historical data.
    """
    if len(costs) < 2:
        # Not enough data to predict
        return dates, costs, []

    # Prepare data for scikit-learn
    # X will be days since start (0, 1, 2...)
    # y will be costs
    X = np.array(range(len(costs))).reshape(-1, 1)
    y = np.array(costs)

    model = LinearRegression()
    model.fit(X, y)

    # Predict for the next `days_to_predict` days
    future_X = np.array(range(len(costs), len(costs) + days_to_predict)).reshape(-1, 1)
    predicted_costs = model.predict(future_X).tolist()
    
    # Ensure no negative costs
    predicted_costs = [max(0.0, float(c)) for c in predicted_costs]

    # Generate future dates
    last_date = datetime.strptime(dates[-1], "%Y-%m-%d")
    future_dates = [(last_date + timedelta(days=i+1)).strftime("%Y-%m-%d") for i in range(days_to_predict)]

    # We return the original dates + future dates, original costs, and predicted costs
    # We will pad predicted_costs so that it aligns with the combined timeline
    all_dates = dates + future_dates
    
    # Pad historical costs with None for future dates
    hist_padded = costs + [None] * days_to_predict
    
    # For a continuous line, the first predicted value could start at the end of historical
    # Alternatively we just pad with None
    pred_padded = [None] * len(costs) + predicted_costs
    
    return all_dates, hist_padded, pred_padded
