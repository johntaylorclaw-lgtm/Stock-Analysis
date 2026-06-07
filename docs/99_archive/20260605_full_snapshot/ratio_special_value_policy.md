# 比率与增长率特殊值编码规范

生成日期：2026-05-31

## 1. 适用范围

本规范适用于工程内所有由“分子 / 分母”生成的事实型比率、增长率、变化率字段，包括：

1. 财务质量比率，例如 `ocf_to_profit_asof`、`goodwill_to_assets_asof`。
2. 财务成长比率，例如 `revenue_yoy_1y_calc_asof`、`roe_change_rate_4report_asof`。
3. 后续其他模块中通过分子和分母构造的比率字段。

普通差值字段不适用本规则，例如：

```text
roe_yoy_change_asof = current_roe - prior_roe
```

这类字段没有除法分母，遇到任一输入缺失时返回 NULL。

## 2. 编码目标

用户建议使用 `-9` 加二进制状态位表达特殊值。该方向是合理的，因为它能把“无法正常计算”的原因保留在数值中，便于宽表分析。

为避免歧义，本工程采用固定 6 位状态码：

```text
-9ABCDEF
```

含义如下：

| 位置 | 含义 | 1 表示 | 0 表示 |
|---|---|---|---|
| A | 分子为 0 | numerator = 0 | numerator != 0 或无法判断 |
| B | 分子为空 | numerator IS NULL | numerator IS NOT NULL |
| C | 分子为负 | numerator < 0 | numerator >= 0 或无法判断 |
| D | 分母为 0 | denominator = 0 | denominator != 0 或无法判断 |
| E | 分母为空 | denominator IS NULL | denominator IS NOT NULL |
| F | 分母为负 | denominator < 0 | denominator >= 0 或无法判断 |

示例：

| 编码 | 含义 |
|---:|---|
| `-9100000` | 分子为 0，分母为正且非空非 0 |
| `-9010000` | 分子为空 |
| `-9001000` | 分子为负，分母为正且非空非 0 |
| `-9000100` | 分母为 0 |
| `-9000010` | 分母为空 |
| `-9000001` | 分母为负 |
| `-9010010` | 分子为空且分母为空 |
| `-9001001` | 分子为负且分母为负 |

你举例中的 `-9010100` 按本规范解释为：

```text
分子为空，分母为 0
```

如果想表达“分子不为 0、不为空、不为负；分母为 0、不为空、不为负”，应写作：

```text
-9000100
```

## 3. 正常值与特殊值边界

当且仅当以下条件同时满足时，返回正常比率值：

```text
numerator IS NOT NULL
AND denominator IS NOT NULL
AND numerator > 0
AND denominator > 0
```

正常比率公式：

```text
ratio = numerator / denominator - offset
```

其中：

1. 普通比率 `offset = 0`。
2. 增长率 `offset = 1`。

只要分子或分母出现 `0`、`NULL`、负值之一，就返回特殊编码。

## 4. 编码值类型

特殊编码以数值 `DOUBLE` 形式写入比率字段，保持宽表直接可用。

同时，数据字典必须在字段说明中标注：

```text
特殊值遵循 -9ABCDEF 编码；正常值为小数比例。
```

后续如需要更严格的类型治理，可以额外增加 `_status_code` 字段，但第一版不强制增加，以避免字段数量膨胀。

## 5. 通用伪代码

```text
special_code(numerator, denominator):
    A = numerator == 0
    B = numerator is null
    C = numerator < 0
    D = denominator == 0
    E = denominator is null
    F = denominator < 0
    return numeric("-9" + A + B + C + D + E + F)

safe_ratio(numerator, denominator, offset):
    if numerator > 0 and denominator > 0:
        return numerator / denominator - offset
    else:
        return special_code(numerator, denominator)
```

## 6. 注意事项

1. 特殊编码是事实分类，不是异常值清洗。
2. 下游模型工程如不希望混用特殊编码，应自行将 `value < -9000000` 的记录转成缺失值或哑变量。
3. 本工程不对特殊编码做 winsorize、标准化或评分处理。
4. 本工程所有新增比率字段必须在数据字典中说明是否使用该规范。
