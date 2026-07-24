# 自包含打包

插件自包含--框架文件(`lib/` / 脚手架 / dll / assets)打包进插件 `assets/`,独立可分发,不依赖 rouge_lua 存在。选自包含而非运行时引用 rouge_lua,为支持分发与他人使用;代价是框架更新需重新打包(用 sync 脚本从 rouge_lua 同步)。二进制(socket.dll/libwinpthread-1.dll/fonts.ttf)全部打包,授权用户自负(NOTICE 标注来源作 courtesy)。
