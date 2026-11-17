---
id: binary-search
name: 二分查找（红蓝染色）
category: 二分
signals: [有序数组, 找第一个满足条件的位置, 数组可按某个判定分成两段, 要求 O(log n)]
problems: [704, 35, 34, 162, 153]
---
## 核心思想
不要背“找 target”，要找**判定函数**：存在一个 `check(i)`，使数组左边一段全为 False（红）、
右边一段全为 True（蓝）。二分要求的就是第一个蓝色的位置。
数组不必整体有序，只要能分成这样两段（162、153 就是这种情况）。

## 模板：lower_bound，开区间写法
```python
def lower_bound(nums, target):
    left, right = -1, len(nums)      # 不变量：left 一直是红，right 一直是蓝
    while left + 1 < right:          # 区间 (left, right) 不为空
        mid = (left + right) // 2
        if nums[mid] >= target:      # check(mid)：是蓝
            right = mid
        else:
            left = mid
    return right                     # 第一个 >= target 的下标；可能等于 len(nums)
```

## 四种需求都化归为 lower_bound
| 需求 | 写法 |
|---|---|
| 第一个 `>= x` | `lower_bound(x)` |
| 第一个 `> x` | `lower_bound(x + 1)`（整数） |
| 最后一个 `< x` | `lower_bound(x) - 1` |
| 最后一个 `<= x` | `lower_bound(x + 1) - 1` |

## 易错点
- 返回值可能越界（`len(nums)` 或 `-1`），使用前先判断。34 要再检查 `nums[i] == target`。
- 153 拿 `nums[mid]` 和 `nums[-1]` 比，而不是和 `nums[0]` 比；想清楚“蓝色”的定义再写。
- 开区间写法里 `left`/`right` 从不会被当作答案去访问 `nums`，这就是选它的原因。
