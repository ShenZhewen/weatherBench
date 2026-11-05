# -*- coding: utf-8 -*-
r"""把 scores 下的全量 CSV 瘦化成按 metric 分片的 JSON，供 index.html 静态复刻站使用。

支持两个数据源（用 --src 切换，一次只出一个产物）：
  --src=det  (默认)  读 scores/scores_all.csv   -> data/<det metric>.json  确定性评分
  --src=prob         读 scores/prob_all.csv     -> data/<prob metric>.json 概率评分(crps/spread_skill/unbiased_mean_rmse)

每源一次生成若干文件（det:7 / prob:3），每个含该 metric 下全部
truth / resolution / year / variable@level / model 的 (lead, value) 曲线向量，
浏览器端按需 fetch 单个 metric 文件即可展示所有选择组合。

输出结构：
    {
      "models":  {model: 展示名, ...},
      "cat":     {model: det|ens, ...},
      "refs":    {truth: 参考标签, ...},          # era5->ERA5, hres_t0->Analysis
      "names":   {varkey: {levels:[...], unit:...}, ...},
      "resolutions": [...], "years": [...],
      "series":  {truth: {res: {year: {varkey: {model: [[lead,value],...]}}}}}
    }

用法（仓库根）：
    python prep.py --src=det   # 确定性 -> data/rmse.json 等 7 个
    python prep.py --src=prob  # 概率   -> data/crps.json 等 3 个
"""
import argparse
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(HERE, 'data')

# ----------------------------- model 展示名 -----------------------------
# model 内部名 -> 图例展示名（含参考线统一风格）。det / prob 两套。
# 展示名对齐官方 deterministic-scores 页（combine_results.py 的
# DETERMINISTIC_MODELS 映射）。官方页把内部名 arcana 显示为 Tianji。
MODEL_LONG = {
    'ens_mean': 'IFS ENS (mean)',
    'ens_single_member': 'IFS ENS (1st member)',
    'era5_forecast': 'ERA5-Forecasts',
    'graphcast': 'GraphCast',
    'graphcast_hres_init': 'GraphCast (oper.)',
    'hres': 'IFS HRES',
    'pangu': 'Pangu-Weather',
    'pangu_hres_init': 'Pangu-Weather (oper.)',
    'persistence': 'Persistence',
    'swin': 'Swin',
    'climatology': 'Climatology',
    'fuxi': 'FuXi',
    'aurora': 'Aurora (oper.)',
    'gencast_mean': 'GenCast (mean)',
    'gencast_single_member': 'GenCast (1st member)',
    'gencast_operational_mean': 'GenCast (oper.) (mean)',
    'gencast_operational_single_member': 'GenCast (oper.) (1st member)',
    'gencast_operational_100m_uv_mean': 'GenCast (oper.) (mean)',
    'gencast_operational_100m_uv_single_member': 'GenCast (oper.) (1st member)',
    'fgn_operational_mean': 'FGN (oper.) (mean)',
    'fgn_operational_single_member': 'FGN (oper.) (1st member)',
    'weathermesh4': 'WeatherMesh4',
    'astra_mean': 'Astra (mean)',
    'astra_single_member': 'Astra (1st member)',
    'arcana': 'Tianji',
    'excarta': 'Excarta (HEAL-ViT)',
    'baguan': 'Baguan',
    'keisler': 'Keisler (2022)',
    'neuralgcm_ens_mean': 'NeuralGCM ENS (mean)',
    'neuralgcm_ens_single_member': 'NeuralGCM ENS (1st member)',
    'neuralgcm_hres': 'NeuralGCM 0.7',
    'stormer_ens_mean': 'Stormer ENS (mean)',
    'arches_weather': 'ArchesWeather',
    'arches_weather_gen_mean': 'ArchesWeatherGen (mean)',
    'arches_weather_mx4': 'ArchesWeather-Mx4',
    'tongyun': 'TongYun',
}
# 概率榜的模型内部名（prob_all.csv 里的 model 列）
MODEL_LONG_PROB = {
    'ens': 'IFS ENS',
    'probabilistic_climatology': 'Probabilistic Climatology',
    'gencast': 'GenCast',
    'gencast_operational': 'GenCast (oper.)',
    'gencast_operational_100m_uv': 'GenCast (oper., 100m-uv)',
    'fgn_operational': 'FGN (oper.)',
    'astra': 'Astra',
    'neuralgcm_ens': 'NeuralGCM (ens.)',
    'arches_weather_gen': 'ArchesWeather (gen.)',
}

# truth -> 参考线标签（与目标站 Analysis / ERA5 语义对齐）
REF_LABEL = {'era5': 'ERA5', 'hres_t0': 'Analysis'}

# 集合预测模型集合（含集合 mean 与单 member）；其余为确定性模型。
# 仅对 det 源生效。prob 源里所有模型都是 ensemble。
# 不进站点的模型：官方 deterministic 榜里 "GenCast (oper.)" 对应的是
# gencast_operational_100m_uv_*；另有一套不加 100m_uv 的老跑法
# （gencast_operational_mean / _single_member），显示名会和官方条目撞车，
# 数据仍保留在 scores_all.csv 里，只是不在网页上画。
HIDDEN_MODELS = {
    'gencast_operational_mean', 'gencast_operational_single_member',
}

ENS_MODELS = {
    'ens_mean', 'ens_single_member',
    'gencast_mean', 'gencast_single_member',
    'gencast_operational_mean', 'gencast_operational_single_member',
    'gencast_operational_100m_uv_mean', 'gencast_operational_100m_uv_single_member',
    'fgn_operational_mean', 'fgn_operational_single_member',
    'astra_mean', 'astra_single_member',
    'neuralgcm_ens_mean', 'neuralgcm_ens_single_member',
    'stormer_ens_mean', 'arches_weather_gen_mean', 'arches_weather_mx4',
}


def parse_csv(path):
    """读 CSV -> (metrics[metric][truth][res][year][vkey][model][lead]=val,
                 models, vars_, resolutions, years) 全部在内存累积。"""
    metrics = {}
    models = {}
    vars_ = {}
    resolutions = set()
    years = set()
    with open(path, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            m = row['metric']; truth = row['truth']; res = row['resolution']
            yr = row['year']; var = row['var']; lvl = row['level']
            lead = int(row['lead_h']); val = float(row['value']); unit = row['unit']
            vkey = var if lvl == '-1' else '%s@%s' % (var, lvl)

            model = row['model']
            if model in HIDDEN_MODELS:
                continue
            metrics.setdefault(m, {}).setdefault(truth, {}).setdefault(res, {}) \
                   .setdefault(yr, {}).setdefault(vkey, {}).setdefault(model, {})[lead] = val

            if model not in models:
                models[model] = MODEL_LONG_PROB.get(model) or MODEL_LONG.get(model, model)
            v = vars_.setdefault(vkey, {'levels': set(), 'unit': ''})
            # 同一变量的单位随 metric 变（tp 的 acc 是空、mse 是 mm²/step、rmse 是 mm/6h），
            # 统一取 rmse 的单位；没有 rmse 时取第一个非空单位。
            if unit and (m == 'rmse' or not v['unit']):
                v['unit'] = unit
            if lvl != '-1':
                v['levels'].add(int(lvl))
            else:
                v['levels'].add(-1)
            resolutions.add(res); years.add(yr)
    return metrics, models, vars_, resolutions, years


def build(content):
    """content[truth][res][year][vkey][model][lead] -> nested dict, innermost
    as sorted [[lead,value],...]. Explicit loops (a single nested dict-comp
    would flatten and overwrite outer keys)."""
    out = {}
    for truth, by_r in content.items():
        tr = out.setdefault(truth, {})
        for res, by_y in by_r.items():
            rs = tr.setdefault(res, {})
            for yr, by_v in by_y.items():
                ys = rs.setdefault(yr, {})
                for vkey, by_m in by_v.items():
                    ys[vkey] = {model: sorted(vs.items())
                                for model, vs in sorted(by_m.items())}
    return out


def availability(metrics):
    """metric -> {vkey: ['<res>|<year>', ...]}：有数据的组合，供下拉框过滤空指标。"""
    out = {}
    for m, by_truth in metrics.items():
        by_var = {}
        for by_res in by_truth.values():
            for res, by_year in by_res.items():
                for yr, by_v in by_year.items():
                    for vkey, by_model in by_v.items():
                        if any(pts for pts in by_model.values()):
                            by_var.setdefault(vkey, set()).add(res + '|' + yr)
        out[m] = {k: sorted(v) for k, v in by_var.items()}
    return out


def run(src):
    if src == 'prob':
        csv_path = os.path.join(ROOT, 'scores', 'prob_all.csv')
        is_all_ens = True
    else:
        csv_path = os.path.join(ROOT, 'scores', 'scores_all.csv')
        is_all_ens = False
    metrics, models, vars_, resolutions, years = parse_csv(csv_path)

    os.makedirs(OUT, exist_ok=True)

    if is_all_ens:
        cat = {m: 'ens' for m in models}
    else:
        cat = {m: 'ens' if m in ENS_MODELS else 'det' for m in models}

    sizes = {}
    for m, content in metrics.items():
        payload = {
            'models': models,
            'cat': cat,
            'refs': REF_LABEL,
            'names': {vkey: {'unit': v['unit'],
                             'levels': sorted(v['levels'])} for vkey, v in sorted(vars_.items())},
            'resolutions': sorted(resolutions),
            'years': sorted(years),
            'series': build(content),
        }
        path = os.path.join(OUT, '%s.json' % m)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, separators=(',', ':'))
        sizes[m] = os.path.getsize(path)
    avail_path = os.path.join(OUT, 'availability_%s.json' % src)
    with open(avail_path, 'w', encoding='utf-8') as f:
        json.dump(availability(metrics), f, separators=(',', ':'))
    total = sum(sizes.values())
    print('[%s] %s' % (src, csv_path))
    print('wrote %d metric files -> %s (+ %s, %.1f KB)'
          % (len(sizes), OUT, os.path.basename(avail_path),
             os.path.getsize(avail_path) / 1e3))
    for m, b in sorted(sizes.items(), key=lambda x: -x[1]):
        print('  %-26s %6.1f MB' % (m, b / 1e6))
    print('  total %5.1f MB' % (total / 1e6))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', choices=['det', 'prob'], default='det')
    a = ap.parse_args()
    run(a.src)