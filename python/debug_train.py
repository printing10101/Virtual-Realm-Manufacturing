import requests
import json

resp = requests.post(
    "http://localhost:8000/api/v1/lnn/train",
    json={
        "model_name": "cutting_force",
        "data_path": "C:\\Users\\Lenovo\\AppData\\Local\\Temp\\uniwear.csv",
        "hyperparameters": {
            "epochs": 5,
            "batch_size": 32,
            "learning_rate": 0.001,
            "hidden_size": 64,
        },
        "device": "cpu",
    },
    timeout=10,
)
print("Status:", resp.status_code)
print("Body:", json.dumps(resp.json(), indent=2, ensure_ascii=False))
