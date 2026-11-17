---
id: grid-dfs
name: 网格图 DFS
category: 网格图
signals: [二维网格, 连通块/岛屿, 从边界出发能到达哪些格子]
problems: [200, 695, 463, 130, 1020]
---
## 核心思想
把每个格子看成图上的点，上下左右相邻就连边。“数岛屿”就是数连通块：
从每个没访问过的陆地出发做一次 DFS，把整块标记掉，计数加一。

## 模板
```python
def count_islands(grid):
    m, n = len(grid), len(grid[0])

    def dfs(i, j):
        if not (0 <= i < m and 0 <= j < n) or grid[i][j] != "1":
            return                   # 越界、是水或已访问，统一在入口判断
        grid[i][j] = "2"             # 原地标记已访问（题目允许修改时）
        for di, dj in (0, 1), (0, -1), (1, 0), (-1, 0):
            dfs(i + di, j + dj)

    ans = 0
    for i in range(m):
        for j in range(n):
            if grid[i][j] == "1":
                dfs(i, j)
                ans += 1
    return ans
```

## 变体
- **求面积（695）**：让 `dfs` 返回这块的格子数。
- **从边界出发（130、1020）**：反过来想，先从四条边上的陆地 DFS，标记“能连到边界”的格子，剩下的才是被围住的。
- **周长（463）**：不用 DFS，数每块陆地有几条边挨着水或越界即可。

## 易错点
- Python 递归深度默认约 1000，网格 300×300 可能爆栈：调 `sys.setrecursionlimit`，或改成显式栈/BFS。
- 不能修改输入时，另开 `visited` 数组。
- 字符网格是 `"1"` 不是 `1`，类型对不上会静默出错。
