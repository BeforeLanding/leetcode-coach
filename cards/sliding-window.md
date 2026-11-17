---
id: sliding-window
name: 不定长滑动窗口
category: 滑动窗口与双指针
signals: [连续子数组/子串, 求最长或最短或计数, 窗口性质随扩张单调变化]
problems: [3, 209, 713, 1004, 904]
---
## 核心思想
枚举右端点 `right`，让左端点 `left` 只往右走。成立的前提是**单调性**：
窗口 `[left, right]` 合法 ⇒ 任何更短的 `[left', right]`（left' ≥ left）也合法。
于是每个元素最多进窗口一次、出窗口一次，总复杂度 O(n)。

## 模板（求最长合法窗口）
```python
def longest(nums):
    ans = left = 0
    state = ...                      # 窗口内的统计量：计数、和、哈希表等
    for right, x in enumerate(nums):
        add(state, x)                # 1. 右端点入窗
        while not valid(state):      # 2. 不合法就收缩左端点
            remove(state, nums[left])
            left += 1
        ans = max(ans, right - left + 1)  # 3. 此时窗口合法，更新答案
    return ans
```

## 三种变体，区别只在第 3 步
| 求什么 | 收缩条件 | 更新答案的位置 |
|---|---|---|
| 最长 | 不合法时收缩 | 收缩**之后** |
| 最短 | 合法时收缩 | 收缩循环**里面**（每次收缩前） |
| 计数（以 right 结尾的合法子数组个数） | 不合法时收缩 | 收缩之后 `ans += right - left + 1` |

## 易错点
- 先确认单调性。数组里有负数时“和 ≥ k”就不再单调（这时去看前缀和）。
- 求最短时，初始答案设为 `inf`，最后判断是否仍为 `inf`。
- 计数型（如 713）要注意 `k <= 1` 的边界：乘积不可能 < 1，while 可能把 left 推过 right。
