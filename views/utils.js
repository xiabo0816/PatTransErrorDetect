function section_navs_init() {
    var path = _find_file_blob('sections')
    _read_file(path, function(e) {
        var navlist = JSON.parse(this.result)
        navlist.forEach(element => {
            $('#section-navs').append('<li><a href="#' + element[0] + '" data-stat="' + element[1] + '" onclick="section_nav_onclick(this)">' + element[0] + '</a></li>')
        });
    })
}

function section_nav_onclick(obj) {
    console.log(obj)
    $('#section-navs li').each(function(a) { $($(this)[0]).removeClass('active') })
    $('.tab-pane').each(function(a) { $($(this)[0]).removeClass('active') })
    $($('.tab-pane')[1]).addClass('active')
    $(obj).parent().addClass('active')
    if (obj.dataset.stat == 'poly') {
        treemap_init(obj.innerText)
    }
    table_init(obj.innerText)

}

function home_dashboard_init() {
    var PieChart = echarts.init($('#概览 div:nth-child(2) div')[0]);
    var path = _find_file_blob('stats')
    _read_file(path, function(e) {
        PieChart.setOption(pieoption(JSON.parse(this.result)))
    })
}

function pieoption(data) {
    var legend = [];
    var series_data = [];
    for (let index = 0; index < data.length; index++) {
        const element = data[index];
        legend.push(element.name)
        series_data.push({
            value: element.value,
            name: element.name
        })
    }
    return {
        title: {
            text: '翻译锚点分布图',
            // subtext: '共',
            left: 'center'
        },
        tooltip: {
            trigger: 'item',
            formatter: '{a} <br/>{b} : {c} ({d}%)'
        },
        legend: {
            orient: 'vertical',
            left: 'left',
            data: legend
        },
        series: [{
            name: '访问来源',
            type: 'pie',
            radius: '55%',
            center: ['50%', '60%'],
            data: series_data,
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowOffsetX: 0,
                    shadowColor: 'rgba(0, 0, 0, 0.5)'
                }
            }
        }],
        color: ['#c23531', '#2f4554', '#61a0a8', '#d48265', '#91c7ae', '#749f83', '#ca8622', '#bda29a', '#6e7074', '#546570', '#c4ccd3']
    };
}

function treemap_init(name) {

    function colorMappingChange(value) {
        var levelOption = getLevelOption(value);
        chart.setOption({
            series: [{
                levels: levelOption
            }]
        });
    }

    function getLevelOption() {
        return [{
            itemStyle: {
                borderWidth: 0,
                gapWidth: 5
            }
        }, {
            itemStyle: {
                gapWidth: 1
            }
        }, {
            colorSaturation: [0.35, 0.5],
            itemStyle: {
                gapWidth: 1,
                borderColorSaturation: 0.6
            }
        }];
    }

    var MainChart = echarts.init(document.getElementById('treemap'));
    MainChart.showLoading();
    var path = _find_file_blob('stats')
    _read_file(path, function(e) {
        MainChart.hideLoading();
        var data = JSON.parse(this.result)
        var series_data_id = 0
        for (let index = 0; index < data.length; index++) {
            const element = data[index];
            if (name == element.name) {
                series_data_id = index
            }
        }

        MainChart.setOption(option = {

            title: {
                text: name,
                left: 'center'
            },

            tooltip: {
                formatter: function(info) {
                    var value = info.value;
                    var treePathInfo = info.treePathInfo;
                    var treePath = [];

                    for (var i = 1; i < treePathInfo.length; i++) {
                        treePath.push(treePathInfo[i].name);
                    }

                    return [
                        '<div class="tooltip-title">' + echarts.format.encodeHTML(treePath.join('/')) + '</div>',
                        '复现: ' + echarts.format.addCommas(value) + ' 次',
                    ].join('');
                }
            },

            series: [{
                name: name,
                type: 'treemap',
                visibleMin: 300,
                label: {
                    show: true,
                    formatter: '{b}'
                },
                itemStyle: {
                    borderColor: '#fff'
                },
                levels: getLevelOption(),
                data: data[series_data_id].children,
            }],
            color: ['#c23531', '#2f4554', '#61a0a8', '#d48265', '#91c7ae', '#749f83', '#ca8622', '#bda29a', '#6e7074', '#546570', '#c4ccd3']
        });

        treemap_bind_onclick(MainChart)
    })

}


function treemap_bind_onclick(MainChart) {
    var uploadedDataURL = 'disk.tree.json';

    MainChart.on('click', function(params) {
        // 控制台打印数据的名称
        // console.log(params);
        var path_items = undefined
        if (params.hasOwnProperty('data') && params.data.hasOwnProperty('path')) {
            path_items = []
            path_items = params.data.path.split("/")
        }
        if (params.hasOwnProperty('treePathInfo')) {
            path_items = []
            path_items[0] = ''
            if (params.treePathInfo.hasOwnProperty(1)) {
                path_items[1] = params.treePathInfo[1].name
            }
            if (params.treePathInfo.hasOwnProperty(2)) {
                path_items[2] = params.treePathInfo[2].name
            }
        }
        if (path_items == undefined)
            return

        switch (path_items.length) {
            case 3:
                $('#table').bootstrapTable('filterBy', {
                    name: path_items[1],
                    obj: path_items[2]
                })
                break;
            case 2:
                $('#table').bootstrapTable('filterBy', {
                    name: path_items[1],
                })
                break;

            default:
                $('#table').bootstrapTable('filterBy', {})
                break;
        }
    });
}

function table_init(name) {
    var indexfile = []
    var index = []

    _read_file(_find_file_blob(name + '.id'), function(e) {
        index = JSON.parse(this.result)
        _read_file(_find_file_blob(name + '.idx'), function(e) {
            indexfile = JSON.parse(this.result)
            $('#table').bootstrapTable({
                // url: 'data1.json',
                pagination: true,
                search: "true",
                columns: [{
                    field: 'name',
                    title: 'name',
                    searchable: "true"
                }, {
                    field: 'obj',
                    title: 'obj',
                    formatter: function(value, row) {
                        return '<textarea disabled>' + _HTMLEncode(value) + '</textarea>'
                    },
                    searchable: "true"
                }, {
                    field: 'index',
                    title: 'input_ori_file',
                    searchable: "true",
                    formatter: function(value, row) {
                        console.log(value)
                        if ("input_ori_file" in indexfile[value.id])
                            return indexfile[value.id].input_ori_file;
                        else
                            return value
                    },
                }, {
                    field: 'index',
                    title: 'input_trans_file',
                    searchable: "true",
                    formatter: function(value, row) {
                        console.log(value)
                        if ("input_trans_file" in indexfile[value.id])
                            return indexfile[value.id].input_trans_file
                        else
                            return value
                    },
                }, {
                    field: 'index',
                    title: 'c_origin',
                    formatter: function(value, row) {
                        return '<textarea disabled>' + _HTMLEncode(index[value.idx].c_origin) + '</textarea>'
                    },
                    searchable: "true"
                }, {
                    field: 'index',
                    title: 'c_trans',
                    formatter: function(value, row) {
                        return '<textarea disabled>' + _HTMLEncode(index[value.idx].c_trans) + '</textarea>'
                    },
                    searchable: "true"
                }],
                onClickCell: function(field, value, row, $element) {
                    // console.log(field, value, row, $element)
                    if ($element[0].innerText.endWith('.XML')) {
                        window.open($('#toolbar_pathpfx').val() + $element[0].innerText);
                    }
                }
            })

            _read_file(_find_file_blob(name + '.details'), function(e) {
                $('#table').bootstrapTable('load', JSON.parse(this.result));
            })

        })
    })




}

function _read_file(path, callback) {
    var reader = new FileReader();
    reader.readAsText(path);
    reader.onload = callback
}

function _find_file_blob(str) {
    var files = document.getElementById("file").files;

    for (var i = 0; f = files[i]; i++) {
        if (f.name == str + '.json') {
            return f
        }
    }
    return false
}

function _HTMLEncode(html) {
    var temp = document.createElement("div");
    (temp.textContent != null) ? (temp.textContent = html) : (temp.innerText = html);
    var output = temp.innerHTML;
    temp = null;
    return output;
}

String.prototype.endWith = function(s) {
    if (s == null || s == "" || this.length == 0 || s.length > this.length)
        return false;
    if (this.substring(this.length - s.length) == s)
        return true;
    else
        return false;
    return true;
};