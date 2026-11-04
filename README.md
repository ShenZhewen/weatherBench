# WeatherBench · WeatherBench2 评分复刻站

静态复刻 Google [WeatherBench2 评分站](https://sites.research.google/gr/weatherbench/deterministic-scores/)，
纯静态（无后端），托管在 GitHub Pages。

## 包含

- **Deterministic scores**：官方模型 × 6 指标（ACC/Bias/Forecast Activity/MSE/RMSE/SEEPS，
  与官方 deterministic 页一致，默认 RMSE）× 3 分辨率（1440x721/240x121/64x32）× 3 年份（2018/2020/2022）
  × 2 参考（ERA5/Analysis）
  额外加入 **TongYun** 的 2022 年 z500（ERA5 参考、1440x721）
- **Probabilistic scores**：9 个概率模型 × 5 指标（CRPS/Spread/Skill/Unbiased Spread/Unbiased Mean RMSE/Mean RMSE）

## 数据

- 原始评分数据：全部 373 个官方 `benchmark_results/*.nc`（`scripts/wb2_fetch_scores.py` 从
  `gs://weatherbench2` 拉取）
- 确定性长表：`scores/scores_all.csv`（`scripts/wb2_benchmark_scores.py` 解析）
- TongYun z500：由 `scores/TongYun_nc/wb2_2022_z500_deterministic.nc` 追加进 `scores_all.csv`
  （model=tongyun，year=2022，truth=era5，level=500；rmse 由 sqrt(mse) 得到）。
  当前这份是 2022 全年 699 个起报的结果（2022-01-01 00Z – 12-16 12Z，6h 间隔，lead 6–360h）。
- 概率长表：`scores/prob_all.csv`（`scripts/wb2_prob2csv.py` 解析）
- 站点 JSON：由 `prep.py --src=det|prob` 从上述 CSV 瘦化生成到 `data/`

## 本地预览

```bash
python -m http.server 8000   # 在 wb2-site/ 下
```

## 重新生成数据

```bash
python prep.py --src=det     # 生成 data/rmse.json 等
python prep.py --src=prob    # 生成 data/crps.json 等
```