# WeatherBench · WeatherBench2 评分复刻站

静态复刻 Google [WeatherBench2 评分站](https://sites.research.google/gr/weatherbench/deterministic-scores/)，
纯静态（无后端），托管在 GitHub Pages。

## 包含

- **Deterministic scores**：官方模型 × 6 指标（ACC/Bias/Forecast Activity/MSE/RMSE/SEEPS，
  与官方 deterministic 页一致，默认 RMSE）× 3 分辨率（1440x721/240x121/64x32）× 3 年份（2018/2020/2022）
  × 2 参考（ERA5/Analysis）
  额外加入 **TongYun** 的 2022 年 z500（ERA5 参考、1440x721）
- **WeatherBenchX 补充指标**（目前只有 TongYun 有行）：Error Exceedance、Relative Intensity，
  以及降水（total_precipitation_6hr）的 CSI / Frequency Bias / FSS（≥1/5/10 mm per 6h，FSS 邻域 9 px）。
  由 `scripts/wb2_extra_metrics.py` 后处理生成，定义对齐 WeatherBenchX（面积加权、按 init 平均）
- **Probabilistic scores**：9 个概率模型 × 5 指标（CRPS/Spread/Skill/Unbiased Spread/Unbiased Mean RMSE/Mean RMSE）

## 数据

- 原始评分数据：全部 373 个官方 `benchmark_results/*.nc`（`scripts/wb2_fetch_scores.py` 从
  `gs://weatherbench2` 拉取）
- 确定性长表：`scores/scores_all.csv`（`scripts/wb2_benchmark_scores.py` 解析）
- TongYun 确定性评分：`scores/TongYun_nc/wb2_2022_<var>_deterministic.nc`（11 个变量：z500、
  q700、t700、t850、t2m、msl、u850、v850、u10、v10、tp）由 `scripts/wb2_tongyun_nc2csv.py`
  追加进 `scores_all.csv`（model=tongyun，year=2022，truth=era5，resolution=1440x721；
  rmse 由 sqrt(mse) 得到；tp 从 m 换算成 mm/6h）。
  当前这份是 2022 全年 700 个起报的结果（2022-01-01 00Z – 12-16 12Z，12h 间隔，lead 6–360h）。
- TongYun 补充指标：`scripts/wb2_extra_metrics.py` 在服务器上直接从 forecast/truth/climatology
  zarr 算出长表 CSV（表头与 `scores_all.csv` 完全一致），与该目录下的 `wb2_2022_extra.csv`
  一起由 `scripts/wb2_tongyun_nc2csv.py` 合并进 `scores_all.csv`，再跑 `prep.py --src=det`。
  阈值是脚本顶部的字面量：`ERROR_EXCEEDANCE_THRESHOLD`（z500 50 gpm、温度 5 K、风 5 m/s、
  msl 5 hPa、q 1.5 g/kg、降水 5 mm/6h）、`PRECIP_THRESHOLDS_MM`、`FSS_NEIGHBORHOOD_PX`。
- 概率长表：`scores/prob_all.csv`（`scripts/wb2_prob2csv.py` 解析）
- 站点 JSON：由 `prep.py --src=det|prob` 从上述 CSV 瘦化生成到 `data/`
- 指标可用性索引：同一命令同时生成 `data/availability_<src>.json`（指标 -> 有数据的
  变量/分辨率/年份组合），前端据此隐藏当前选择下一条线都没有的指标选项

## 本地预览

```bash
python -m http.server 8000   # 在 wb2-site/ 下
```

## 重新生成数据

```bash
python prep.py --src=det     # 生成 data/rmse.json 等
python prep.py --src=prob    # 生成 data/crps.json 等
```