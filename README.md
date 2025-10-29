## DeserAnalyzer
### 项目介绍
本项目GCSCAN：多语言反序列化漏洞链检测与分析平台采用更先进的静态分析技术，实现对应用程序中反序列化漏洞链的高效全面检测；并通过集成多语言分析工具，支持Java、PHP语言项目的扫描检测。此外，GCSCAN还提供在线审计、AI辅助研判及宏观统计分析等功能，全面赋能软件应用的安全检测。

### 环境依赖
- Java：17
- 使用git lfs下载jadx依赖

### 效果预览
主页效果如图
![主页](./flask_app/assets/images/index.jpg)

分析页面效果如图
![分析](./flask_app/assets/images/analyze.jpg)

结果页面效果如图
![结果](./flask_app/assets/images/result.jpg)

本系统还支持在线代码审计，及AI辅助审计

### AI 配置
根目录下放置`.env`文件，配置AI辅助审计：
```
AI_BASE_URL=https://api.siliconflow.cn/v1
AI_MODEL=deepseek-ai/DeepSeek-V3.2-Exp
AI_API_KEY=sk-yourkey
```

### 论文支撑
本系统基于如下的Gadget Chain检测工具进行开发：
- PFortifier: Mitigating PHP Object Injection Through Automatic Patch Generation，发表于2025 IEEE Symposium on Security and Privacy (SP)
- Precise and effective gadget chain mining through deserialization guided call graph construction，发表于Proceedings of the 34th USENIX Conference on Security Symposium