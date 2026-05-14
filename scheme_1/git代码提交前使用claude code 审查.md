# git代码提交前使用claude code 审查

# Git提交前使用Claude代码审查指南

## 一、功能概述

本脚本实现代码提交前自动化审查流程，核心功能包括：

1.  自动识别暂存区变更文件
    
2.  智能过滤资源/配置文件
    
3.  调用Claude代码审查服务
    
4.  多级审查结果处理（阻断/警告/通过）
    
5.  飞书实时通知推送
    

## 二、配置说明

### 1、下载claude code

npm install -g @anthropic-ai/claude-code

### 2、配置claude

"C:\Users\Administrator\.claude\settings.json" 打开新增配置属性

 "includeCoAuthoredBy": false;

可以跳过这一步，直接进入第三步

### 3、下载cc-switch，

这文件是配置当前智能[请至钉钉文档查看附件《CC-Switch-v3.11.1-Windows.msi》。](https://alidocs.dingtalk.com/i/nodes/YMyQA2dXW797bn6kUMRLXMwXJzlwrZgb?iframeQuery=anchorId%3DX02mnzyn1dep20m7zh3r2c&utm_scene=person_space)体使用什么模型快捷切换，避免手写json导致失败，

![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/jP2lRYj85EA9LO8g/img/0a389f2a-e004-4137-9714-f0263fc5e280.png)

![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/jP2lRYj85EA9LO8g/img/ef338044-5673-48e9-a831-2823acd8f3f6.png)

![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/jP2lRYj85EA9LO8g/img/f73f787b-d405-4b2f-bec1-920d1215816e.png)

最终的配置文件：{

  "env": {

    "ANTHROPIC\_AUTH\_TOKEN": "6df5271f-2fcb-4b06-bb10-01049e6a5354",

    "ANTHROPIC\_BASE\_URL": "[https://ark.cn-beijing.volces.com/api/coding](https://ark.cn-beijing.volces.com/api/coding)",

    "ANTHROPIC\_DEFAULT\_HAIKU\_MODEL": "deepseek-v3.2",

    "ANTHROPIC\_DEFAULT\_OPUS\_MODEL": "deepseek-v3.2",

    "ANTHROPIC\_DEFAULT\_SONNET\_MODEL": "deepseek-v3.2",

    "ANTHROPIC\_MODEL": "deepseek-v3.2"

  },

  "includeCoAuthoredBy": false

}

### 4、在项目git文件夹修改配置

1、脚本替换地址：[https://alidocs.dingtalk.com/i/nodes/ZX6GRezwJl7G06owcr2QNDodVdqbropQ?utm\_scene=person\_space](https://alidocs.dingtalk.com/i/nodes/ZX6GRezwJl7G06owcr2QNDodVdqbropQ?utm_scene=person_space)

2、文件地址：".git\hooks\pre-commit"修改文件里面的内容进行替换

### 5、在.git 下面新建文件夹：reviews，表现形式为：.git\reviews

这个代码审查文档的最终查看地址

### 6、下载代码审查文件  

1、前端代码审查文件：[请至钉钉文档查看附件《REVIEW\_GUIDELINES\_UI.md》。](https://alidocs.dingtalk.com/i/nodes/YMyQA2dXW797bn6kUMRLXMwXJzlwrZgb?iframeQuery=anchorId%3DX02mnzz04nx9e3npv673t&utm_scene=person_space)

下载放到代码根目录，需要重命名为：                    REVIEW\_GUIDELINES.md

2、后端代码审查文件：[请至钉钉文档查看附件《REVIEW\_GUIDELINES\_SERVER.md》。](https://alidocs.dingtalk.com/i/nodes/YMyQA2dXW797bn6kUMRLXMwXJzlwrZgb?iframeQuery=anchorId%3DX02mnzz0feog9ky3h9v7v&utm_scene=person_space)

下载放到代码根目录，需要重命名为：REVIEW\_GUIDELINES.md

### 7、配置系统环境变量

![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/jP2lRYj85EA9LO8g/img/5ab0b7a3-2587-4a7c-84e3-b621a0aa4a29.png)

新建环境变量：CLAUDE\_CODE\_GIT\_BASH\_PATH，

变量值指向本机 git安装的地址，如D:\Git\bin\bash.exe

![image.png](https://alidocs.oss-cn-zhangjiakou.aliyuncs.com/res/jP2lRYj85EA9LO8g/img/5f1f74f8-d663-4bfb-9808-514d6e89de7a.png)