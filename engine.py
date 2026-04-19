import pandas as pd
import re
import datetime
import pytz

TOKYO_TZ = pytz.timezone('Asia/Tokyo')

def extract_metrics(text):
    if pd.isna(text) or text == "-" or str(text).strip() == "":
        return None, None, None, None
    times = re.findall(r"\d+\.\d+", str(text))
    rank_match = re.search(r"(\d+)着", str(text))
    race_t = float(times[0]) if len(times) >= 1 else None
    trial_t = float(times[1]) if len(times) >= 2 else None
    st = float(times[2]) if len(times) >= 3 else None
    rank = int(rank_match.group(1)) if rank_match else None
    return race_t, trial_t, st, rank

def calculate_predictions(df, place, info_dict, weather_prefix="良5"):
    df = df.copy()

    # 過去5走データの展開
    for i in range(1, 6):
        col_name = f"{weather_prefix}_前{i}"
        if col_name in df.columns:
            metrics = df[col_name].apply(extract_metrics)
            df[f'前競走T_{i}'] = metrics.apply(lambda x: x[0])
            df[f'前試走T_{i}'] = metrics.apply(lambda x: x[1])
            df[f'前ST_{i}'] = metrics.apply(lambda x: x[2])
            df[f'前順位_{i}'] = metrics.apply(lambda x: x[3])

    num_cols = ['試走T', 'ハンデ', '偏差']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 中央値による基本指標の算出
    df['平均競走タイム'] = df[[f'前競走T_{i}' for i in range(1, 6)]].median(axis=1)
    df['平均試走'] = df[[f'前試走T_{i}' for i in range(1, 6)]].median(axis=1)
    df['平均順位'] = df[[f'前順位_{i}' for i in range(1, 6)]].median(axis=1)
    df['平均st'] = df[[f'前ST_{i}' for i in range(1, 6)]].median(axis=1)

    # 1. 基本予想タイム計算
    df['直前予想競走T'] = (df['平均競走タイム'] - df['平均試走']) + df['試走T']

    # 2. 【1号車補正】
    df.loc[df['車'] == 1, '直前予想競走T'] = df.loc[df['車'] == 1, '直前予想競走T'].apply(lambda x: x - 0.01 if pd.notnull(x) else x)

    # 各種評価フラグ・スコアの初期化
    score_cols = ['地元評価', 'ランク評価', '激変評価', '走路温度補正', 'ST評価', '夜間補正', '追い上げスコア', '上昇評価', '逃げ評価', '偏差評価', 'タイム評価', '実績評価']
    for col in score_cols:
        df[col] = 0

    # 環境データの解析
    try:
        temp_val = float(re.search(r'\d+', info_dict.get("走路温度", "0")).group())
        hum_val = float(re.search(r'\d+', info_dict.get("湿度", "0")).group())
    except:
        temp_val, hum_val = 0, 0
    
    current_hour = datetime.datetime.now(TOKYO_TZ).hour

    for i in range(len(df)):
        # 3. 【地元評価】
        if '所属' in df.columns and str(df.loc[i, '所属']) == place:
            df.loc[i, '地元評価'] = 8
        
        # 4. 【精密ランク評価】
        if 'ランク' in df.columns:
            r = str(df.loc[i, 'ランク'])
            match = re.search(r'([SA])\-(\d+)', r)
            if match:
                grade, num = match.group(1), int(match.group(2))
                if grade == 'S':
                    df.loc[i, 'ランク評価'] = 20 if num <= 10 else 15
                elif grade == 'A':
                    df.loc[i, 'ランク評価'] = 10 if num <= 100 else 5

        # 5. 【試走激変評価】
        if pd.notnull(df.loc[i, '試走T']) and pd.notnull(df.loc[i, '平均試走']):
            if df.loc[i, '平均試走'] - df.loc[i, '試走T'] >= 0.03:
                df.loc[i, '激変評価'] = 10

        # 6. 【走路温度補正】
        if temp_val >= 40:
            if 'ランク' in df.columns:
                r_str = str(df.loc[i, 'ランク'])
                if r_str.startswith('S') or (r_str.startswith('A') and re.search(r'A\-(\d+)', r_str) and int(re.search(r'A\-(\d+)', r_str).group(1)) <= 100):
                    df.loc[i, '走路温度補正'] = 5

        # 7. 【夜間・湿度補正】
        if current_hour >= 18 and hum_val >= 60:
            if df.loc[i, 'ランク評価'] >= 10:
                df.loc[i, '夜間補正'] = 5

    # 8. 【ST評価】
    if 'ハンデ' in df.columns:
        for hd in df['ハンデ'].unique():
            if pd.isna(hd): continue
            mask = df['ハンデ'] == hd
            subset = df[mask].sort_values('車')
            if subset.empty: continue
            min_st = subset['平均st'].min()
            if not pd.isna(min_st):
                df.loc[mask & (df['平均st'] == min_st), 'ST評価'] += 10
            for j in range(len(subset) - 1):
                curr_idx, out_idx = subset.index[j], subset.index[j+1]
                if pd.notnull(subset.loc[curr_idx, '平均st']) and pd.notnull(subset.loc[out_idx, '平均st']):
                    if subset.loc[curr_idx, '平均st'] <= (subset.loc[out_idx, '平均st'] + 0.01):
                        df.loc[curr_idx, 'ST評価'] += 7

    # 9. 【試走落差警戒】
    avg_st_rank = df['平均st'].rank(ascending=False)
    best_trial_car = df['試走T'].idxmin()
    if avg_st_rank.loc[best_trial_car] >= (len(df) - 1):
        df.loc[best_trial_car, 'ST評価'] -= 8

    # 10. 【重ハン救済・追い上げ性能】
    df['100m単価'] = df['直前予想競走T'] / 31.0
    for i in range(len(df)):
        my_unit = df.loc[i, '100m単価']
        if pd.isna(my_unit): continue
        predecessors = df.iloc[:i]
        if not predecessors.empty and all(predecessors['100m単価'] > (my_unit + 0.015)):
            df.loc[i, '追い上げスコア'] = 15
        followers = df.iloc[i+1:]
        if not followers.empty and any(followers['100m単価'] < (my_unit - 0.02)):
            df.loc[i, '追い上げスコア'] -= 10

    # 上昇度・逃げ・偏差・タイム・実績
    df['上昇度'] = (df['前競走T_3'] - df['前競走T_2']) + (df['前競走T_2'] - df['前競走T_1'])
    df['上昇評価'] = df['上昇度'].apply(lambda x: 10 if (not pd.isna(x) and x > 0) else (5 if x == 0 else 0))
    for i in range(len(df)):
        if i < 3:
            trial_rank = df['試走T'].rank(method='min').iloc[i]
            if trial_rank <= 2 and df.loc[i, '平均st'] <= 0.15: df.loc[i, '逃げ評価'] = 15
    if '偏差' in df.columns:
        m_dev = df['偏差'].median()
        df['偏差評価'] = df['偏差'].apply(lambda x: 10 if (not pd.isna(x) and x <= m_dev) else 0)
    
    df['タイム順位'] = df['直前予想競走T'].rank(method='min')
    df['タイム評価'] = df['タイム順位'].apply(lambda x: max(0, 60 - (x * 10)) if not pd.isna(x) else 0)
    perf_col = f'{weather_prefix}_平均順位'
    df['実績評価'] = df[perf_col].rank(method='min').apply(lambda x: max(0, 30 - (x * 5))) if perf_col in df.columns else 0

    # 11. 【最終集計】
    df['予想スコア'] = df[score_cols].sum(axis=1)
    
    return df
