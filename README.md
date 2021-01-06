# PatTransErrorDetect
PatTransErrorDetect!

# 工作流程
定义翻译锚点；
原文筛选锚点；
译文对照锚点；
统计排序；

# 锚点选择方案
1. 对照编码表，定义标准原文字符集，再对字符集取反；
2. 归纳总结，数字、尖括号、标点符号、大写字母、实体词典、专名

# 功能设计

## 输入

`config.ini`

包含了一些基本设置，主要是锚点正则表达式们

```python
import configparser
```

`input.list`

待分析原文和译文的文件列表

## 输出

分为两种：

* *.html：识别到错误的文件详情

* *.stat.json：各个翻译锚点的出错点、出错频率

* TODO: 未识别到错误的文件详情；