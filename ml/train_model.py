"""Latih RandomForest risiko banjir dan ekspor ke JSON ringan.

Training memakai scikit-learn di tahap builder Docker. Model yang dikirim ke
tahap runtime bukan binary scikit-learn, melainkan struktur pohon keputusan
dalam JSON. Dengan begitu runtime tidak perlu scipy/scikit-learn dan image
produksi jauh lebih kecil. Inferensi JSON diimplementasikan di app/risk.py.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

FEATURES = [
    "curah_hujan_mm",
    "tma_cm",
    "drainase_skor",
    "elevasi_m",
    "impervious_pct",
]
LABELS = ["Aman", "Waspada", "Siaga", "Awas"]
MODEL_VERSION = "1.0.0"
RANDOM_STATE = 42


def buat_dataset(n_samples: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(RANDOM_STATE)

    curah_hujan = rng.uniform(0, 300, n_samples)
    tma = rng.uniform(50, 500, n_samples)
    drainase = rng.uniform(0, 10, n_samples)
    elevasi = rng.uniform(2, 60, n_samples)
    impervious = rng.uniform(5, 95, n_samples)

    hujan_n = np.clip(curah_hujan / 250.0, 0, 1)
    tma_n = np.clip(tma / 400.0, 0, 1)
    drainase_n = 1.0 - drainase / 10.0
    elevasi_n = 1.0 - np.clip(elevasi / 50.0, 0, 1)
    impervious_n = impervious / 100.0

    interaksi = hujan_n * (0.6 * drainase_n + 0.4 * impervious_n)
    noise = rng.normal(0, 0.035, n_samples)

    risiko = (
        0.30 * hujan_n
        + 0.22 * tma_n
        + 0.15 * drainase_n
        + 0.08 * elevasi_n
        + 0.10 * impervious_n
        + 0.15 * interaksi
        + noise
    )

    q30, q60, q85 = np.quantile(risiko, [0.30, 0.60, 0.85])
    label = np.digitize(risiko, [q30, q60, q85]).astype(int)

    X = np.column_stack([curah_hujan, tma, drainase, elevasi, impervious])
    return X, label


def ekspor_pohon(estimator) -> dict:
    tree = estimator.tree_
    jumlah_node = tree.node_count
    probabilitas: list[list[float]] = []

    for node in range(jumlah_node):
        bobot = tree.value[node][0]
        total = float(np.sum(bobot))
        if total <= 0:
            probabilitas.append([0.25, 0.25, 0.25, 0.25])
        else:
            probabilitas.append(
                [round(float(nilai) / total, 8) for nilai in bobot]
            )

    return {
        "left": tree.children_left.tolist(),
        "right": tree.children_right.tolist(),
        "feature": tree.feature.tolist(),
        "threshold": tree.threshold.astype(float).tolist(),
        "proba": probabilitas,
    }


def inferensi_hutan(model: dict, baris: list[float]) -> list[float]:
    total = [0.0] * len(model["classes"])
    for pohon in model["trees"]:
        node = 0
        while pohon["left"][node] != -1:
            fitur = pohon["feature"][node]
            if baris[fitur] <= pohon["threshold"][node]:
                node = pohon["left"][node]
            else:
                node = pohon["right"][node]
        for indeks, nilai in enumerate(pohon["proba"][node]):
            total[indeks] += nilai
    jumlah_pohon = len(model["trees"])
    return [nilai / jumlah_pohon for nilai in total]


def latih(output_dir: str, n_samples: int, n_trees: int, max_depth: int) -> None:
    X, y = buat_dataset(n_samples)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=n_trees,
        max_depth=max_depth,
        min_samples_leaf=10,
        class_weight="balanced_subsample",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    prediksi = model.predict(X_test)
    akurasi = float(accuracy_score(y_test, prediksi))
    laporan = classification_report(
        y_test, prediksi, target_names=LABELS, output_dict=True, zero_division=0
    )

    artefak = {
        "version": MODEL_VERSION,
        "features": FEATURES,
        "classes": LABELS,
        "n_trees": len(model.estimators_),
        "trees": [ekspor_pohon(estimator) for estimator in model.estimators_],
    }

    # Pastikan inferensi JSON identik dengan predict_proba scikit-learn.
    contoh = X_test[:20]
    referensi = model.predict_proba(contoh)
    hasil_json = np.array(
        [inferensi_hutan(artefak, [float(nilai) for nilai in baris]) for baris in contoh]
    )
    selisih = float(np.max(np.abs(referensi - hasil_json)))
    if selisih > 1e-4:
        raise RuntimeError(f"Inferensi JSON tidak cocok dengan sklearn: {selisih}")

    prediksi_json = np.array(
        [
            int(np.argmax(inferensi_hutan(artefak, [float(nilai) for nilai in baris])))
            for baris in X_test
        ]
    )
    akurasi_json = float(accuracy_score(y_test, prediksi_json))

    os.makedirs(output_dir, exist_ok=True)
    model_path = os.path.join(output_dir, "model.json")
    meta_path = os.path.join(output_dir, "model_meta.json")

    with open(model_path, "w", encoding="utf-8") as file:
        json.dump(artefak, file, separators=(",", ":"))

    ukuran_model = os.path.getsize(model_path)
    meta = {
        "version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": FEATURES,
        "classes": LABELS,
        "n_samples": n_samples,
        "n_trees": len(model.estimators_),
        "max_depth": max_depth,
        "accuracy": round(akurasi, 4),
        "accuracy_json": round(akurasi_json, 4),
        "max_probability_diff": selisih,
        "model_size_bytes": ukuran_model,
        "class_distribution": {
            LABELS[i]: int(np.bincount(y, minlength=4)[i]) for i in range(4)
        },
        "feature_importances": {
            fitur: round(float(bobot), 4)
            for fitur, bobot in zip(FEATURES, model.feature_importances_)
        },
        "classification_report": {
            label: {
                "precision": round(float(laporan[label]["precision"]), 4),
                "recall": round(float(laporan[label]["recall"]), 4),
                "f1-score": round(float(laporan[label]["f1-score"]), 4),
            }
            for label in LABELS
        },
    }
    with open(meta_path, "w", encoding="utf-8") as file:
        json.dump(meta, file, indent=2, ensure_ascii=False)

    print(f"Model JSON disimpan di {model_path} ({ukuran_model / 1024:.1f} KiB)")
    print(f"Akurasi uji sklearn : {akurasi:.4f}")
    print(f"Akurasi uji JSON    : {akurasi_json:.4f}")
    print(f"Selisih probabilitas: {selisih:.2e}")
    print(f"Jumlah pohon        : {len(model.estimators_)}")
    print(json.dumps(meta["class_distribution"], ensure_ascii=False))

    contoh_input = [
        [40, 120, 8, 30, 40],
        [140, 250, 5, 15, 70],
        [210, 340, 3, 8, 85],
        [280, 430, 1, 5, 92],
    ]
    for baris in contoh_input:
        prob = inferensi_hutan(artefak, [float(nilai) for nilai in baris])
        skor = int(round(sum(nilai * indeks for indeks, nilai in enumerate(prob)) / 3 * 100))
        print(f"contoh={baris} -> {LABELS[int(np.argmax(prob))]} ({skor})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="model", help="Direktori artefak model")
    parser.add_argument("--samples", type=int, default=4000)
    parser.add_argument("--trees", type=int, default=40)
    parser.add_argument("--depth", type=int, default=9)
    args = parser.parse_args()
    latih(args.output, args.samples, args.trees, args.depth)


if __name__ == "__main__":
    main()
