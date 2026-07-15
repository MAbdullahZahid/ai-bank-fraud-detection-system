# AI-Based Bank Fraud Detection System
## Machine Learning Pipeline

This folder contains the complete machine learning workflow for the AI-Based Bank Fraud Detection System using the PaySim dataset.

---

# Dataset

Dataset: PaySim Mobile Money Fraud Detection

Total Records: 6,362,620

Features: 11

Target Variable:
- isFraud

---

# Machine Learning Workflow

## 1. Exploratory Data Analysis (EDA)

Purpose:
- Understand dataset structure
- Check data quality
- Analyze fraud distribution
- Visualize important patterns

Performed:
- Dataset overview
- Data types
- Missing value analysis
- Duplicate check
- Class imbalance analysis
- Transaction type analysis
- Correlation analysis
- Distribution analysis
- Feature visualization

Output:
```
eda/plots/
```

---

## 2. Data Preprocessing

Purpose:
Prepare the dataset for machine learning.

Performed:

- Label Encoding
- Feature Engineering
- Balance Difference Features
- Merchant Identification
- Feature Scaling
- Train / Validation / Test Split

Final Features:

- step
- type
- amount
- oldbalanceOrg
- newbalanceOrig
- oldbalanceDest
- newbalanceDest
- isFlaggedFraud
- isMerchant
- balanceOrigDiff
- balanceDestDiff
- errorBalanceOrig
- errorBalanceDest

Generated Files:

```
dataset/processed/

X_train.csv
y_train.csv

X_val.csv
y_val.csv

X_test.csv
y_test.csv
```

Saved Models:

```
models/

label_encoder.joblib
scaler.joblib
```

---

## 3. Model Training

Algorithm Used:

XGBoost Classifier

Configuration:

- Early Stopping
- Class Imbalance Handling (scale_pos_weight)
- Validation Monitoring

Validation Results:

Accuracy : 99.99%

Precision : 94.34%

Recall : 99.77%

F1 Score : 96.98%

ROC-AUC : 99.98%

Generated Files:

```
models/

xgboost_model.joblib
xgboost_feature_importance.png
```

```
reports/

xgboost_metrics.json
```

---

## 4. Overfitting Check

Train ROC-AUC : 1.0000

Validation ROC-AUC : 0.9998

Gap : 0.0002

Result:

No significant overfitting observed.

---

## 5. Threshold Tuning

Different thresholds were evaluated to improve fraud detection performance.

Selected Threshold:

```
0.7
```

Reason:

- Highest Precision
- Excellent Recall
- Highest F1 Score
- Suitable for fraud detection systems

---

## 6. Final Evaluation

The trained model was evaluated on an unseen test dataset.

Current evaluation was performed on 50% of the test data for development purposes.

Results:

Accuracy : 99.99%

Precision : 94.77%

Recall : 99.88%

F1 Score : 97.26%

ROC-AUC : 99.98%

Confusion Matrix:

```
TN = 635400

FP = 45

FN = 1

TP = 816
```

Generated Reports:

```
reports/

final_metrics.json

confusion_matrix.png

roc_curve.png

precision_recall_curve.png
```

---

# Final Saved Model

```
models/

xgboost_model.joblib

scaler.joblib

label_encoder.joblib
```

These files are used by the FastAPI backend for real-time fraud prediction.

---

# Backend Prediction Flow

Frontend
↓

Backend (FastAPI)
↓

Load ML Model

↓

Receive Transaction

↓

Generate Features

↓

Encode + Scale

↓

XGBoost Prediction

↓

Threshold (0.7)

↓

Fraud / Safe

↓

Save Transaction

↓

Return Response