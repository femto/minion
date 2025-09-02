## 🧠 **记忆存储**

### **系统架构记忆**
- never put test in the top level folder
- agent.run_async() 返回的是一个async函数，需要先await才能获得async generator
  - 正确用法: `async for event in (await agent.run_async(input_obj, **kwargs)):`
  - 错误用法: `async for event in agent.run_async(input_obj, **kwargs):`
  - 这是因为run_async是async函数，它delegate到其他函数，本身需要await才能返回真正的async generator

### **开发流程记忆**
- 如果是一定功能的修改的话,尽可能添加test,先跑通test
- 如果非常简单的修改可以不用test
- 另外添加的文件请git add 到版本库里
- 如果是修改examples,也请改完之后试跑该example,修改必要的bug,直到跑通为止