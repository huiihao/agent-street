# Numeric summary
## Condition means (mean, SD)
### static
- aggregateReturn: -0.003016 (SD 0.000530)
- meanMaxDrawdown: -0.016419 (SD 0.000735)
- strategyDiversity: 0.554700 (SD 0.000000)
- returnSD: 0.006705 (SD 0.000982)
- meanTradeSynchrony: 0.855717 (SD 0.010558)
- meanAbsOrderImbalance: 0.756246 (SD 0.019356)
- strategyGeneration: 0.000000 (SD 0.000000)
- totalAdaptations: 0.000000 (SD 0.000000)
- meanWinRate: 0.443553 (SD 0.022863)
- totalTrades: 1396.312500 (SD 20.535234)
- totalConversations: 215.875000 (SD 4.964877)
- guildMomentum: 8.000000 (SD 0.000000)
- guildMeanReversion: 0.000000 (SD 0.000000)
- guildSentiment: 0.000000 (SD 0.000000)
- guildContrarian: 7.000000 (SD 0.000000)
- guildBalanced: 1.000000 (SD 0.000000)
### imitation_only
- aggregateReturn: -0.002520 (SD 0.000556)
- meanMaxDrawdown: -0.016511 (SD 0.000561)
- strategyDiversity: 0.552750 (SD 0.055350)
- returnSD: 0.005290 (SD 0.000772)
- meanTradeSynchrony: 0.875445 (SD 0.013766)
- meanAbsOrderImbalance: 0.797596 (SD 0.019838)
- strategyGeneration: 8.750000 (SD 1.807392)
- totalAdaptations: 36.812500 (SD 5.718027)
- meanWinRate: 0.447251 (SD 0.021844)
- totalTrades: 1344.750000 (SD 20.101410)
- totalConversations: 217.750000 (SD 5.709641)
- guildMomentum: 8.375000 (SD 1.204159)
- guildMeanReversion: 0.812500 (SD 0.750000)
- guildSentiment: 0.000000 (SD 0.000000)
- guildContrarian: 6.375000 (SD 0.885061)
- guildBalanced: 0.437500 (SD 0.512348)
### no_imitation
- aggregateReturn: -0.002370 (SD 0.000843)
- meanMaxDrawdown: -0.014791 (SD 0.000708)
- strategyDiversity: 0.614750 (SD 0.044793)
- returnSD: 0.005194 (SD 0.000858)
- meanTradeSynchrony: 0.794333 (SD 0.013486)
- meanAbsOrderImbalance: 0.642437 (SD 0.025659)
- strategyGeneration: 78.250000 (SD 5.385165)
- totalAdaptations: 612.625000 (SD 20.509754)
- meanWinRate: 0.425959 (SD 0.024350)
- totalTrades: 1451.187500 (SD 25.346186)
- totalConversations: 219.000000 (SD 5.932959)
- guildMomentum: 6.750000 (SD 1.000000)
- guildMeanReversion: 0.750000 (SD 0.774597)
- guildSentiment: 0.875000 (SD 0.806226)
- guildContrarian: 7.000000 (SD 0.000000)
- guildBalanced: 0.625000 (SD 0.500000)
### full
- aggregateReturn: -0.001919 (SD 0.000817)
- meanMaxDrawdown: -0.015579 (SD 0.000843)
- strategyDiversity: 0.623544 (SD 0.061580)
- returnSD: 0.004878 (SD 0.000790)
- meanTradeSynchrony: 0.834128 (SD 0.017464)
- meanAbsOrderImbalance: 0.713073 (SD 0.034860)
- strategyGeneration: 75.687500 (SD 7.777907)
- totalAdaptations: 607.750000 (SD 28.508478)
- meanWinRate: 0.440262 (SD 0.016095)
- totalTrades: 1399.312500 (SD 37.918718)
- totalConversations: 216.812500 (SD 5.394055)
- guildMomentum: 6.062500 (SD 1.526161)
- guildMeanReversion: 1.687500 (SD 1.537043)
- guildSentiment: 0.312500 (SD 0.478714)
- guildContrarian: 7.062500 (SD 0.928709)
- guildBalanced: 0.875000 (SD 0.806226)

## Primary paired tests
- full - static | aggregateReturn: a=-0.001919, b=-0.003016, diff=0.001097 [0.000619,0.001658], p=7.748e-04, holm=3.099e-03, rb=0.956
- full - static | meanMaxDrawdown: a=-0.015579, b=-0.016419, diff=0.000840 [0.000316,0.001326], p=4.181e-03, holm=8.289e-03, rb=0.779
- full - static | strategyDiversity: a=0.623544, b=0.554700, diff=0.068844 [0.038094,0.097144], p=4.145e-03, holm=8.289e-03, rb=0.867
- full - static | returnSD: a=0.004878, b=0.006705, diff=-0.001826 [-0.002445,-0.001178], p=3.052e-04, holm=1.831e-03, rb=-0.926
- full - static | meanTradeSynchrony: a=0.834128, b=0.855717, diff=-0.021589 [-0.031971,-0.011601], p=1.312e-03, holm=3.937e-03, rb=-0.853
- full - static | meanAbsOrderImbalance: a=0.713073, b=0.756246, diff=-0.043173 [-0.062296,-0.024380], p=5.798e-04, holm=2.899e-03, rb=-0.897
- no_imitation - static | aggregateReturn: a=-0.002370, b=-0.003016, diff=0.000646 [0.000215,0.001044], p=1.825e-02, holm=1.825e-02, rb=0.662
- no_imitation - static | meanMaxDrawdown: a=-0.014791, b=-0.016419, diff=0.001627 [0.001180,0.002044], p=3.052e-05, holm=1.831e-04, rb=1.000
- no_imitation - static | strategyDiversity: a=0.614750, b=0.554700, diff=0.060050 [0.039056,0.081044], p=2.106e-03, holm=4.213e-03, rb=1.000
- no_imitation - static | returnSD: a=0.005194, b=0.006705, diff=-0.001511 [-0.002157,-0.000923], p=5.798e-04, holm=1.740e-03, rb=-0.897
- no_imitation - static | meanTradeSynchrony: a=0.794333, b=0.855717, diff=-0.061384 [-0.070763,-0.050898], p=3.052e-05, holm=1.831e-04, rb=-1.000
- no_imitation - static | meanAbsOrderImbalance: a=0.642437, b=0.756246, diff=-0.113809 [-0.131677,-0.094964], p=3.052e-05, holm=1.831e-04, rb=-1.000
- imitation_only - static | aggregateReturn: a=-0.002520, b=-0.003016, diff=0.000496 [0.000165,0.000869], p=1.059e-02, holm=3.178e-02, rb=0.750
- imitation_only - static | meanMaxDrawdown: a=-0.016511, b=-0.016419, diff=-0.000092 [-0.000389,0.000224], p=3.755e-01, holm=7.509e-01, rb=-0.265
- imitation_only - static | strategyDiversity: a=0.552750, b=0.554700, diff=-0.001950 [-0.029287,0.023431], p=1.000e+00, holm=1.000e+00, rb=0.000
- imitation_only - static | returnSD: a=0.005290, b=0.006705, diff=-0.001414 [-0.002068,-0.000751], p=1.312e-03, holm=5.249e-03, rb=-0.853
- imitation_only - static | meanTradeSynchrony: a=0.875445, b=0.855717, diff=0.019729 [0.012287,0.027561], p=1.526e-04, holm=7.629e-04, rb=0.956
- imitation_only - static | meanAbsOrderImbalance: a=0.797596, b=0.756246, diff=0.041349 [0.029043,0.054282], p=3.052e-05, holm=1.831e-04, rb=1.000
- full - no_imitation | aggregateReturn: a=-0.001919, b=-0.002370, diff=0.000451 [0.000021,0.000897], p=1.787e-01, holm=5.362e-01, rb=0.382
- full - no_imitation | meanMaxDrawdown: a=-0.015579, b=-0.014791, diff=-0.000788 [-0.001245,-0.000349], p=5.157e-03, holm=2.063e-02, rb=-0.765
- full - no_imitation | strategyDiversity: a=0.623544, b=0.614750, diff=0.008794 [-0.026844,0.045400], p=8.422e-01, holm=8.422e-01, rb=0.058
- full - no_imitation | returnSD: a=0.004878, b=0.005194, diff=-0.000315 [-0.000771,0.000100], p=3.225e-01, holm=6.450e-01, rb=-0.294
- full - no_imitation | meanTradeSynchrony: a=0.834128, b=0.794333, diff=0.039795 [0.030844,0.048912], p=6.104e-05, holm=3.052e-04, rb=0.985
- full - no_imitation | meanAbsOrderImbalance: a=0.713073, b=0.642437, diff=0.070636 [0.053991,0.088809], p=3.052e-05, holm=1.831e-04, rb=1.000
- full - imitation_only | aggregateReturn: a=-0.001919, b=-0.002520, diff=0.000601 [0.000189,0.001046], p=2.137e-02, holm=4.274e-02, rb=0.654
- full - imitation_only | meanMaxDrawdown: a=-0.015579, b=-0.016511, diff=0.000932 [0.000484,0.001398], p=7.629e-04, holm=3.052e-03, rb=0.882
- full - imitation_only | strategyDiversity: a=0.623544, b=0.552750, diff=0.070794 [0.035162,0.110325], p=4.442e-03, holm=1.333e-02, rb=0.809
- full - imitation_only | returnSD: a=0.004878, b=0.005290, diff=-0.000412 [-0.000800,-0.000063], p=5.768e-02, holm=5.768e-02, rb=-0.544
- full - imitation_only | meanTradeSynchrony: a=0.834128, b=0.875445, diff=-0.041317 [-0.052926,-0.030115], p=3.052e-05, holm=1.831e-04, rb=-1.000
- full - imitation_only | meanAbsOrderImbalance: a=0.713073, b=0.797596, diff=-0.084523 [-0.105436,-0.063893], p=3.052e-05, holm=1.831e-04, rb=-1.000

## Guild composition
     condition  momentum  mean_reversion  sentiment  contrarian  balanced
        static     8.000           0.000      0.000       7.000     1.000
imitation_only     8.375           0.812      0.000       6.375     0.438
  no_imitation     6.750           0.750      0.875       7.000     0.625
          full     6.062           1.688      0.312       7.062     0.875

## Observer run-level
- v1 | cascadeScore -> futureSynchrony: rho=0.0290, p=8.199e-01, CI[-0.2387,0.3116], n=64
- v1 | cascadeScore -> futureAbsImbalance: rho=0.0445, p=7.272e-01, CI[-0.2158,0.3283], n=64
- v1 | cascadeScore -> futureAbsDD: rho=-0.1326, p=2.961e-01, CI[-0.3906,0.1504], n=64
- v1 | cascadeScore -> futureReturn: rho=-0.0762, p=5.496e-01, CI[-0.3213,0.1841], n=64
- v1 | polarization -> futureSynchrony: rho=-0.5564, p=1.812e-06, CI[-0.7058,-0.3646], n=64
- v1 | polarization -> futureAbsImbalance: rho=-0.5395, p=4.233e-06, CI[-0.6986,-0.3445], n=64
- v1 | polarization -> futureAbsDD: rho=-0.5464, p=2.999e-06, CI[-0.6997,-0.3432], n=64
- v1 | polarization -> futureReturn: rho=0.1099, p=3.874e-01, CI[-0.1446,0.3596], n=64
- v1 | imitationRecent -> futureSynchrony: rho=0.5852, p=3.796e-07, CI[0.3702,0.7441], n=64
- v1 | imitationRecent -> futureAbsImbalance: rho=0.6227, p=3.919e-08, CI[0.4199,0.7742], n=64
- v1 | imitationRecent -> futureAbsDD: rho=0.5259, p=8.090e-06, CI[0.3227,0.6813], n=64
- v1 | imitationRecent -> futureReturn: rho=0.1811, p=1.520e-01, CI[-0.0700,0.4194], n=64
- v1 | currentSynchrony -> futureSynchrony: rho=0.6729, p=1.123e-09, CI[0.4996,0.7973], n=64
- v1 | currentSynchrony -> futureAbsImbalance: rho=0.6730, p=1.117e-09, CI[0.4985,0.7979], n=64
- v1 | currentSynchrony -> futureAbsDD: rho=0.4932, p=3.467e-05, CI[0.2659,0.6744], n=64
- v1 | currentSynchrony -> futureReturn: rho=0.0031, p=9.807e-01, CI[-0.2362,0.2378], n=64
- v1 | currentAbsImbalance -> futureSynchrony: rho=0.7100, p=5.053e-11, CI[0.5399,0.8249], n=64
- v1 | currentAbsImbalance -> futureAbsImbalance: rho=0.7115, p=4.427e-11, CI[0.5292,0.8272], n=64
- v1 | currentAbsImbalance -> futureAbsDD: rho=0.4740, p=7.620e-05, CI[0.2489,0.6557], n=64
- v1 | currentAbsImbalance -> futureReturn: rho=-0.0178, p=8.888e-01, CI[-0.2805,0.2338], n=64
- v2 | cascadeScore -> futureSynchrony: rho=0.0290, p=8.199e-01, CI[-0.2387,0.3116], n=64
- v2 | cascadeScore -> futureAbsImbalance: rho=0.0445, p=7.272e-01, CI[-0.2158,0.3283], n=64
- v2 | cascadeScore -> futureAbsDD: rho=-0.1326, p=2.961e-01, CI[-0.3906,0.1504], n=64
- v2 | cascadeScore -> futureReturn: rho=-0.0762, p=5.496e-01, CI[-0.3213,0.1841], n=64
- v2 | flowRiskScore -> futureSynchrony: rho=0.7539, p=6.466e-13, CI[0.5923,0.8639], n=64
- v2 | flowRiskScore -> futureAbsImbalance: rho=0.7695, p=1.100e-13, CI[0.6116,0.8704], n=64
- v2 | flowRiskScore -> futureAbsDD: rho=0.6086, p=9.543e-08, CI[0.4031,0.7570], n=64
- v2 | flowRiskScore -> futureReturn: rho=0.0897, p=4.809e-01, CI[-0.1478,0.3189], n=64
- v2 | flowSynchrony -> futureSynchrony: rho=0.6728, p=1.131e-09, CI[0.4942,0.7970], n=64
- v2 | flowSynchrony -> futureAbsImbalance: rho=0.6726, p=1.149e-09, CI[0.4934,0.7985], n=64
- v2 | flowSynchrony -> futureAbsDD: rho=0.4921, p=3.633e-05, CI[0.2548,0.6804], n=64
- v2 | flowSynchrony -> futureReturn: rho=0.0027, p=9.830e-01, CI[-0.2338,0.2460], n=64
- v2 | flowImbalance -> futureSynchrony: rho=0.7100, p=5.053e-11, CI[0.5483,0.8193], n=64
- v2 | flowImbalance -> futureAbsImbalance: rho=0.7115, p=4.427e-11, CI[0.5405,0.8277], n=64
- v2 | flowImbalance -> futureAbsDD: rho=0.4740, p=7.620e-05, CI[0.2606,0.6541], n=64
- v2 | flowImbalance -> futureReturn: rho=-0.0178, p=8.888e-01, CI[-0.2718,0.2317], n=64
- v2 | polarization -> futureSynchrony: rho=-0.5564, p=1.812e-06, CI[-0.7074,-0.3602], n=64
- v2 | polarization -> futureAbsImbalance: rho=-0.5395, p=4.233e-06, CI[-0.6972,-0.3328], n=64
- v2 | polarization -> futureAbsDD: rho=-0.5464, p=2.999e-06, CI[-0.7032,-0.3533], n=64
- v2 | polarization -> futureReturn: rho=0.1099, p=3.874e-01, CI[-0.1291,0.3506], n=64
- v2 | imitationRecent -> futureSynchrony: rho=0.5852, p=3.796e-07, CI[0.3704,0.7456], n=64
- v2 | imitationRecent -> futureAbsImbalance: rho=0.6227, p=3.919e-08, CI[0.4169,0.7718], n=64
- v2 | imitationRecent -> futureAbsDD: rho=0.5259, p=8.090e-06, CI[0.3222,0.6802], n=64
- v2 | imitationRecent -> futureReturn: rho=0.1811, p=1.520e-01, CI[-0.0739,0.4114], n=64
- v2 | currentSynchrony -> futureSynchrony: rho=0.6729, p=1.123e-09, CI[0.5021,0.7955], n=64
- v2 | currentSynchrony -> futureAbsImbalance: rho=0.6730, p=1.117e-09, CI[0.5021,0.7936], n=64
- v2 | currentSynchrony -> futureAbsDD: rho=0.4932, p=3.467e-05, CI[0.2603,0.6838], n=64
- v2 | currentSynchrony -> futureReturn: rho=0.0031, p=9.807e-01, CI[-0.2408,0.2458], n=64
- v2 | currentAbsImbalance -> futureSynchrony: rho=0.7100, p=5.053e-11, CI[0.5374,0.8244], n=64
- v2 | currentAbsImbalance -> futureAbsImbalance: rho=0.7115, p=4.427e-11, CI[0.5447,0.8249], n=64
- v2 | currentAbsImbalance -> futureAbsDD: rho=0.4740, p=7.620e-05, CI[0.2498,0.6567], n=64
- v2 | currentAbsImbalance -> futureReturn: rho=-0.0178, p=8.888e-01, CI[-0.2658,0.2361], n=64

## Reliability
{
  "runs": 64,
  "all_weight_sums_ok": true,
  "all_trust_symmetric": true,
  "all_conversation_participants_ok": true,
  "all_trades_valid": true,
  "all_tick_metrics_finite": true,
  "total_invariant_failures": 0,
  "min_agents": 16,
  "min_observers": 4
}

## Snapshot
{
  "sha256": "3c9cf0ff864b68e6886c1f3181f67e6e93dbacef8102007c34fedc768c9f86fe",
  "source": "yfinance",
  "bars": 390,
  "first_utc": "2026-10-13T13:30:00+00:00",
  "last_utc": "2026-10-19T19:55:00+00:00",
  "interval": "5m",
  "days_back": 5
}
{
  "AAPL": 0.0,
  "GOOGL": 0.0,
  "MSFT": 0.0,
  "TSLA": 0.0,
  "AMZN": 0.0
}
