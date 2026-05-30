from ultralytics import YOLO
from pathlib import Path

def train_radar_model():
    data_path = r'Exp_Redo_D_E/yaml/train/'
    exp_base_name = Path(data_path).stem   # 例如 "E"
    
    seeds = [1, 42, 123, 2026, 999, 4, 30, 88, 101, 666]
    # seeds = [ 88, 101, 666]
    for i, s in enumerate(seeds):
        print(f"\n开始第 {i+1}/{len(seeds)} 次训练，使用随机种子: {s}")
        model = YOLO('yolov8n.pt')
        current_exp_name = f"{exp_base_name}_Seed_{s}"
        model.train(
            data=data_path,
            epochs=100,
            imgsz=(1024, 512),
            batch=16,
            device=0,
            project='project_DE_errorbar',
            name=current_exp_name,
            seed=s,
            deterministic=True,
        )
        print(f"第 {i+1} 次训练完成！结果保存在 project_DE_errorbar/{current_exp_name}")

if __name__ == '__main__':
    train_radar_model()