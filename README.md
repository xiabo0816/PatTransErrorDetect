
该项目不再维护。

最新项目的地址[在这里](https://gitee.com/xiabo0816/pat-trans-error-detect)

# 专利机翻检测工具

专利机翻检测工具，用于辅助发现机翻中的疑似问题，方便进一步处理。

[线上地址](https://github.com/xiabo0816/PatTransErrorDetect)

如果想做多人分工，可以将输入内容做分块，[分块方法在：操作流程->检测工具->input.list](###`input.list`)

包括检测工具和可视化工具两部分，
* 检测工具需要做安装配置，用于生成待分析的*.json文件
* 可视化工具不需要，仅需拷贝views/目录、待分析的*.json文件

# 技术路线
* 定义翻译锚点，锚点选择方案：
1. 对照编码表，定义标准锚点字符集；
2. 归纳总结，数字块、HTML实体、缩写、序号、等式、非规范引用等；
3. 对照符号串，在*原文*和*译文*中对这些锚点符号串进行对照；
4. 如果未对照出现，则认为有错误
* 原文筛选锚点；
* 译文对照锚点；
* 统计排序；

# 翻译锚点中的符号

目前专利XML文件统一使用utf8编码，属于unicode编码方案的实现方案之一。

计算机内部，所有信息最终都是一个二进制值。在这个编码方案中，它为每种语言中的每个字符设定了统一并且唯一的二进制编码，能够表示世界上所有的书写语言中可能用於电脑通讯的字元、象形文字和其他符号，满足了跨语言、跨平台进行文本转换、处理的要求。

目前一共收录了109449个符号(Unicode v7.0)，其中的中日韩文字为74500个。可以近似认为，全世界现有的符号当中，三分之二以上来自东亚文字，汉字就多达10万左右。比如，中文"好"的码点是十六进制的"597D"。

这么多的字符，不是一个一个定义的，而是分区定义，共分成308区，每个区可以存放若干个字符。这些分区基本按照文字和符号两大类进行划分，文字类就包括欧洲字、东亚字、南亚字、中亚字等，符号类就包括数学运算符、杂项工业符号、带圈或括号的字母数字等。

我们将其中可作为翻译锚点的若干符号类字符区进行疑似匹配，也就是先在原文中识别之后再到译文中进行匹配。

具体来说，作为翻译锚点的字符区包括：数学运算符、工业符号、上标及下标、带圈或括号的字母数字、占位修饰符号、中日韩符号和标点、结合附加符号、结合附加符号补充、货币符号等共18区。

字符示例可以查看字符集标准https://www.unicode.org/charts/，

或者中文站点https://unicode-table.com/cn/blocks/。

# TODO 
- [x] CA数据
- [x] excel导出
- [x] 分布概览导出
- [x] 分布图和树图颜色
- [x] 输入文件夹目录
- [x] 导出错误文件log
- [x] 区分安装文档和使用文档
- [x] escape=(.sub.|.sup.)
- [x] 输入excel格式
- [x] 输入txt格式
- [x] 输出txt中间锚点文件
- [x] CA参考文献

- [x] 扩展缩写词集
- [x] csv打开时乱码
- [x] 合并每个段落中识别相同的锚点，并添加总数列
- [x] 增加概览图数据表
- [x] 使用bat批处理文件包装固定
- [x] 优化KR参考文献
- [x] 优化AT参考文献
- [x] 修正碱基匹配误差
- [x] 识别缩写

- [ ] escape_pfx=(by weight|by mass|by wt\.)
- [ ] escape_sfx=()
- [ ] 化学式
- [ ] 氨基酸核苷酸序列
- [ ] csv中的逗号错误，数字格式12345或者12,345
- [ ] 可否在可视化界面和其关联的原文件中对不匹配的内容自动进行高亮显示，而不需要手动搜索？