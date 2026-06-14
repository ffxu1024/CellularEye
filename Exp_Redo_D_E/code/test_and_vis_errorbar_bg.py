import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from ultralytics import YOLO
from pathlib import Path

# ================= 1. Path configuration =================
PROJECT_DIR = Path('runs/detect/project_DE_errorbar')
YAML_DIR = Path('Exps/Exp_Redo_D_E/yaml/test')

SCENARIO_MAP = {
    "test_D.yaml": "Cross-BS",
    "test_E.yaml": "Cross-Beam"
}

METRICS = ['mAP50', 'mAP50-95', 'Precision', 'Recall']

# ================= 2. Evaluation logic =================
def run_full_evaluation():
    all_results = []
    val_root = PROJECT_DIR / 'val_results'
    val_root.mkdir(parents=True, exist_ok=True)

    for yaml_name, label in SCENARIO_MAP.items():
        test_yaml_path = YAML_DIR / yaml_name
        if not test_yaml_path.exists():
            continue

        scenario_key = yaml_name.split('_')[1].split('.')[0]   # "D" or "E"
        # search_configs = [
        #     {"prefix": "baseline_Seed_*", "model_type": "Baseline"},
        #     {"prefix": f"{scenario_key}_Seed_*", "model_type": "Ours"},
        #     {"prefix": f"{scenario_key}_emptybg_Seed_*", "model_type": "Empty BG"}
        # ]
        search_configs = [
            {"prefix": f"{scenario_key}_baseline_Seed_*", "model_type": "Baseline"},
            {"prefix": f"{scenario_key}_Seed_*", "model_type": "Real+Sim aug."},
            {"prefix": f"{scenario_key}_emptybg_Seed_*", "model_type": "BG aug."}
        ]
        for cfg in search_configs:
            model_folders = list(PROJECT_DIR.glob(cfg['prefix']))
            for folder in model_folders:
                weights = folder / 'weights' / 'best.pt'
                if not weights.exists():
                    continue

                print(f"🔎 Evaluating: {folder.name} on {yaml_name}")
                model = YOLO(weights)
                val_save_name = f"{folder.name}_{yaml_name.replace('.yaml', '')}"
                metrics = model.val(
                    data=str(test_yaml_path),
                    device=0,
                    imgsz=(1024, 512),
                    project=str(val_root),
                    name=val_save_name,
                    exist_ok=True,
                    verbose=False
                )

                all_results.append({
                    "Model": cfg['model_type'],
                    "Scenario": label,
                    "mAP50": metrics.box.map50,
                    "mAP50-95": metrics.box.map,
                    "Precision": metrics.box.mp,
                    "Recall": metrics.box.mr,
                    "Seed": folder.name.split('_')[-1]
                })
    return pd.DataFrame(all_results)


# ================= 3. Plotting logic (Ours on the right) =================
def draw_default_style_plots(df):
    sns.set_theme(style="whitegrid", font_scale=1.3)
    plt.rcParams['font.family'] = 'sans-serif'

    color_dict = {'Baseline': '#1f77b4', 'Empty BG': '#2ca02c', 'Ours': '#ff7f0e'}
    hue_order = ['Baseline', 'Empty BG', 'Ours']

    fig, axes = plt.subplots(1, 4, figsize=(24, 6))

    for idx, metric in enumerate(METRICS):
        ax = axes[idx]

        sns.barplot(
            data=df,
            x="Scenario",
            y=metric,
            hue="Model",
            hue_order=hue_order,
            ax=ax,
            width=0.7,
            capsize=.1,
            #errorbar="sd",
            errorbar=('pi', 100),
            errwidth=1.5,
            edgecolor=".2",
            palette=color_dict
        )

        for patch in ax.patches:
            patch.set_alpha(0.7)

        x_tick_labels = [tick.get_text() for tick in ax.get_xticklabels()]
        n_scenarios = len(x_tick_labels)

        y_max = ax.get_ylim()[1]
        offset = y_max * 0.065

        for i, sc in enumerate(x_tick_labels):
            b_mean = df[(df['Scenario'] == sc) & (df['Model'] == 'Baseline')][metric].mean()
            o_mean = df[(df['Scenario'] == sc) & (df['Model'] == 'Ours')][metric].mean()
            if pd.notnull(b_mean) and pd.notnull(o_mean) and b_mean > 0:
                ours_idx = n_scenarios * 2 + i
                if ours_idx < len(ax.patches):
                    patch = ax.patches[ours_idx]
                    x_center = patch.get_x() + patch.get_width() / 2.0
                    gain = (o_mean - b_mean) / b_mean * 100
                    ax.text(x_center, o_mean + offset, f'+{gain:.1f}%',
                            ha='center', va='bottom', fontweight='bold', fontsize=13)

        ax.set_title('')
        ax.set_ylabel(metric, fontsize=14)
        ax.set_xlabel('')
        ax.set_ylim(0, max(df[metric].max() * 1.2, 0.8) + offset * 1.5)
        ax.get_legend().remove()

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(0.5, 1.08),
               title='Model', ncol=3, frameon=True)

    plt.tight_layout()
    plt.subplots_adjust(top=0.88)

    # Save the figure as PDF.
    save_fig = PROJECT_DIR / 'all_metrics_with_emptybg.pdf'
    plt.savefig(save_fig, dpi=300, bbox_inches='tight', format='pdf')
    print(f"📊 PDF chart saved to: {save_fig}")
    plt.show()


if __name__ == '__main__':
    print("🚀 Starting batch performance evaluation (including the empty background experiment, with Ours on the right)...")
    df_results = run_full_evaluation()
    if not df_results.empty:
        df_results.to_csv(PROJECT_DIR / 'all_seed_results_with_emptybg.csv', index=False)
        print("🎨 Generating comparison plots...")
        draw_default_style_plots(df_results)
    else:
        print("❌ No data detected.")