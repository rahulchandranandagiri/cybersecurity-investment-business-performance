"""Business-impact risk models compared in the study.

All learners estimate P(material business impact | firm context, threat pattern)
from pre-incident fields only; outcome fields (attributes, records, impact) are
never used as inputs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold

from .decision_intelligence import rule_score

SEED = 42
ACT_COLS = ["act_hacking", "act_malware", "act_social", "act_misuse", "act_error",
            "act_physical", "act_environmental", "act_unknown"]


class LookupModel(BaseEstimator, ClassifierMixin):
    """Historical MBI rate per action-category combination (Laplace-smoothed)."""

    def fit(self, X: pd.DataFrame, y):
        key = X[ACT_COLS].astype(int).astype(str).agg("".join, axis=1)
        y = np.asarray(y)
        self.prior_ = y.mean()
        tab = pd.DataFrame({"k": key.values, "y": y}).groupby("k")["y"].agg(["sum", "count"])
        self.rate_ = ((tab["sum"] + self.prior_ * 2) / (tab["count"] + 2)).to_dict()
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X: pd.DataFrame):
        key = X[ACT_COLS].astype(int).astype(str).agg("".join, axis=1)
        p = key.map(self.rate_).fillna(self.prior_).to_numpy(float)
        return np.column_stack([1 - p, p])


class RuleModel(BaseEstimator, ClassifierMixin):
    """Expert consequence rules with Platt scaling (weights are not learned)."""

    def fit(self, X: pd.DataFrame, y):
        self.cal_ = LogisticRegression().fit(rule_score(X).reshape(-1, 1), y)
        self.classes_ = np.array([0, 1])
        return self

    def predict_proba(self, X: pd.DataFrame):
        return self.cal_.predict_proba(rule_score(X).reshape(-1, 1))


def _hgb() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300,
                                          max_leaf_nodes=15, min_samples_leaf=20,
                                          l2_regularization=1.0, random_state=SEED)


def model_zoo() -> dict:
    """name -> (estimator, uses_knowledge_features)."""
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    return {
        "Historical lookup (action category)": (LookupModel(), False),
        "Knowledge rules (expert, calibrated)": (RuleModel(), True),
        "Logistic regression": (GridSearchCV(
            LogisticRegression(max_iter=5000), {"C": [0.03, 0.1, 0.3, 1.0, 3.0]},
            scoring="roc_auc", cv=cv), False),
        "Random forest": (RandomForestClassifier(
            n_estimators=500, min_samples_leaf=3, max_features="sqrt", n_jobs=-1,
            random_state=SEED), False),
        "Gradient boosting": (_hgb(), False),
        "KB-CIDS risk model (GB + knowledge, calibrated)": (CalibratedClassifierCV(
            _hgb(), method="isotonic", cv=cv), True),
    }


def kb_risk_model() -> CalibratedClassifierCV:
    """The proposed risk model used inside the decision layer."""
    return CalibratedClassifierCV(_hgb(), method="isotonic",
                                  cv=StratifiedKFold(5, shuffle=True, random_state=SEED))
