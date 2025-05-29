import os
import openai
import glob
import shutil
import tiktoken
# Agent used to synthesize a final report from the individual summaries.
from pydantic import BaseModel
import time
from agents import Agent
from openai import AsyncOpenAI
from agents import Agent, WebSearchTool
from agents.model_settings import ModelSettings
from agents import Agent, OpenAIResponsesModel, WebSearchTool # 可能还需要导入其他东西
from agents import OpenAIChatCompletionsModel,Agent,Runner,set_default_openai_client, set_tracing_disabled
from agents.model_settings import ModelSettings
from pydantic import BaseModel
from agents import Agent, WebSearchTool
from agents.model_settings import ModelSettings
import numpy as np
import pandas as pd
import pymysql
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv(override=True)
import nest_asyncio
nest_asyncio.apply()  # 允许事件循环嵌套
from agents import function_tool
import asyncio
import json
import io
import inspect
import requests
import re
import random
import string
import base64

import dateutil.parser as parser
import tiktoken

import sys
from dotenv import load_dotenv
from openai import OpenAI

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

os.environ['HTTP_PROXY'] = 'http://127.0.0.1:7890'
os.environ['HTTPS_PROXY'] = 'http://127.0.0.1:7890'

class WebSearchItem(BaseModel):
    reason: str
    "Your reasoning for why this search is important to the query."

    query: str
    "The search term to use for the web search."

class WebSearchPlan(BaseModel):
    searches: list[WebSearchItem]
    """A list of web searches to perform to best answer the query."""

class ReportData(BaseModel):
    short_summary: str
    """A short 2-3 sentence summary of the findings."""

    markdown_report: str
    """The final report"""

    follow_up_questions: list[str]
    """Suggested topics to research further"""

class VastOcean:
    def __init__(self,messages=None):
        # 导入必要的库
        import json
        import os
        import re
        import pymysql
        from openai import OpenAI
        # 设定 token 上限
        self.MAX_TOKENS_LIMIT = 12000 
        # 加载环境变量
        load_dotenv(override=True)
        # 模型API-KEY及请求地址
        self.API_KEY = os.getenv("API_KEY")
        self.MODEL = os.getenv("MODEL")
        self.BASE_URL = os.getenv("BASE_URL")

        self.github_token = os.getenv('GITHUB_TOKEN')
        self.bocha_web_search_api=os.getenv("BOCHA_WEB_SEARCH_API")
        # 谷歌搜索服务器
        self.google_search_key = os.getenv("GOOGLE_SEARCH_API_KEY")
        self.cse_id = os.getenv("CSE_ID") # 
        self.search_user_agent = os.getenv("search_user_agent")
        self.host = os.getenv('HOST')
        self.user = os.getenv('USER')
        self.mysql_pw = os.getenv('MYSQL_PW')
        self.db = os.getenv('DB_NAME')
        self.port = os.getenv('PORT')
        self.python_inter_args = '{"py_code": "import numpy as np\\narr = np.array([1, 2, 3, 4])\\nsum_arr = np.sum(arr)\\nsum_arr"}'
        self.python_inter_tool = {
            "type": "function",
            "function": {
                "name": "python_inter",
                "description": f"当用户需要编写Python程序并执行时，请调用该函数。该函数可以执行一段Python代码并返回最终结果，需要注意，本函数只能执行非绘图类的代码，若是绘图相关代码，则需要调用fig_inter函数运行。\n同时需要注意，编写外部函数的参数消息时，必须是满足json格式的字符串，例如如以下形式字符串就是合规字符串：{self.python_inter_args}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "py_code": {
                            "type": "string",
                            "description": "The Python code to execute."
                        },
                        "g": {
                            "type": "string",
                            "description": "Global environment variables, default to globals().",
                            "default": "globals()"
                        }
                    },
                    "required": ["py_code"]
                }
            }
        } 
        self.fig_inter_tool = {
            "type": "function",
            "function": {
                "name": "fig_inter",
                "description": (
                    "当用户需要使用 Python 进行可视化绘图任务时，请调用该函数。"
                    "该函数会执行用户提供的 Python 绘图代码，并自动将生成的图像对象保存为图片文件并展示。\n\n"
                    "调用该函数时，请传入以下参数：\n\n"
                    "1. `py_code`: 一个字符串形式的 Python 绘图代码，**必须是完整、可独立运行的脚本**，"
                    "代码必须创建并返回一个命名为 `fname` 的 matplotlib 图像对象；\n"
                    "2. `fname`: 图像对象的变量名（字符串形式），例如 'fig'；\n"
                    "3. `g`: 全局变量环境，默认保持为 'globals()' 即可。\n\n"
                    "📌 请确保绘图代码满足以下要求：\n"
                    "- 包含所有必要的 import（如 `import matplotlib.pyplot as plt`, `import seaborn as sns` 等）；\n"
                    "- 必须包含数据定义（如 `df = pd.DataFrame(...)`），不要依赖外部变量；\n"
                    "- 推荐使用 `fig, ax = plt.subplots()` 显式创建图像；\n"
                    "- 使用 `ax` 对象进行绘图操作（例如：`sns.lineplot(..., ax=ax)`）；\n"
                    "- 最后明确将图像对象保存为 `fname` 变量（如 `fig = plt.gcf()`）。\n\n"
                    "📌 不需要自己保存图像，函数会自动保存并展示。\n\n"
                    "✅ 合规示例代码：\n"
                    "```python\n"
                    "import matplotlib.pyplot as plt\n"
                    "import seaborn as sns\n"
                    "import pandas as pd\n\n"
                    "df = pd.DataFrame({'x': [1, 2, 3], 'y': [4, 5, 6]})\n"
                    "fig, ax = plt.subplots()\n"
                    "sns.lineplot(data=df, x='x', y='y', ax=ax)\n"
                    "ax.set_title('Line Plot')\n"
                    "fig = plt.gcf()  # 一定要赋值给 fname 指定的变量名\n"
                    "```"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "py_code": {
                            "type": "string",
                            "description": (
                                "需要执行的 Python 绘图代码（字符串形式）。"
                                "代码必须创建一个 matplotlib 图像对象，并赋值为 `fname` 所指定的变量名。"
                            )
                        },
                        "fname": {
                            "type": "string",
                            "description": "图像对象的变量名（例如 'fig'），代码中必须使用这个变量名保存绘图对象。"
                        },
                        "g": {
                            "type": "string",
                            "description": "运行环境变量，默认保持为 'globals()' 即可。",
                            "default": "globals()"
                        }
                    },
                    "required": ["py_code", "fname"]
                }
            }
        }
        self.sql_inter_args = '{"sql_query": "SHOW TABLES;"}'
        self.sql_inter_tool = {
            "type": "function",
            "function": {
                "name": "sql_inter",
                "description": (
                    "当用户需要进行数据库查询工作时，请调用该函数。"
                    "该函数用于在指定MySQL服务器上运行一段SQL代码，完成数据查询相关工作，"
                    "并且当前函数是使用pymsql连接MySQL数据库。"
                    "本函数只负责运行SQL代码并进行数据查询，若要进行数据提取，则使用另一个extract_data函数。"
                    "同时需要注意，编写外部函数的参数消息时，必须是满足json格式的字符串，例如以下形式字符串就是合规字符串："
                    f"{self.sql_inter_args}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "The SQL query to execute in MySQL database."
                        },
                        "g": {
                            "type": "string",
                            "description": "Global environment variables, default to globals().",
                            "default": "globals()"
                        }
                    },
                    "required": ["sql_query"]
                }
            }
        }
        self.extract_data_args = '{"sql_query": "SELECT * FROM users", "df_name": "users"}'
        self.extract_data_tool = {
            "type": "function",
            "function": {
                "name": "extract_data",
                "description": (
                    "用于在MySQL数据库中提取一张表到当前Python环境中，注意，本函数只负责数据表的提取，"
                    "并不负责数据查询，若需要在MySQL中进行数据查询，请使用sql_inter函数。"
                    "同时需要注意，编写外部函数的参数消息时，必须是满足json格式的字符串，"
                    f"例如如以下形式字符串就是合规字符串：{self.extract_data_args}"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "The SQL query to extract a table from MySQL database."
                        },
                        "df_name": {
                            "type": "string",
                            "description": "The name of the variable to store the extracted table in the local environment."
                        },
                        "g": {
                            "type": "string",
                            "description": "Global environment variables, default to globals().",
                            "default": "globals()"
                        }
                    },
                    "required": ["sql_query", "df_name"]
                }
            }
        }
        self.get_answer_tool = {
            "type": "function",
            "function": {
                "name": "get_answer",
                "description": (
                    "联网搜索工具，当用户提出的问题超出你的知识库范畴时，或该问题你不知道答案的时候，请调用该函数来获得问题的答案。该函数会自动从互联网上搜索得到问题相关文本，而后你可围绕文本内容进行总结，并回答用户提问。需要注意的是，当用户点名要求想要了解GitHub上的项目时候，请调用get_answer_github函数。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "q": {
                            "type": "string",
                            "description": "一个满足搜索格式的问题，用字符串形式进行表示。",
                            "example": "什么是MCP?"
                        },
                        "g": {
                            "type": "string",
                            "description": "Global environment variables, default to globals().",
                            "default": "globals()"
                        }
                    },
                    "required": ["q"]
                }
            }
        }
        self.get_answer_github_tool = {
            "type": "function",
            "function": {
                "name": "get_answer_github",
                "description": (
                    "GitHub联网搜索工具，当用户提出的问题超出你的知识库范畴时，或该问题你不知道答案的时候，请调用该函数来获得问题的答案。"
                    "该函数会自动从GitHub上搜索得到问题相关文本，而后你可围绕文本内容进行总结，并回答用户提问。"
                    "需要注意的是，当用户提问点名要求在GitHub进行搜索时，例如'请帮我介绍下GitHub上的Qwen3项目'，此时请调用该函数，"
                    "其他情况下请调用get_answer外部函数并进行回答。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "q": {
                            "type": "string",
                            "description": "一个满足GitHub搜索格式的问题，往往是需要从用户问题中提出一个适合搜索的项目关键词，用字符串形式进行表示。",
                            "example": "DeepSeek-R1"
                        },
                        "g": {
                            "type": "string",
                            "description": "Global environment variables, default to globals().",
                            "default": "globals()"
                        }
                    },
                    "required": ["q"]
                }
            }
        }
        self.prompt_style1 = """
        你是一名专业且细致的助手，你的任务是在用户提出问题后，通过友好且有引导性的追问，更深入地理解用户真正的需求背景。这样，你才能提供更精准和更有效的帮助。
        当用户提出一个宽泛或者不够明确的问题时，你应当积极主动地提出后续问题，引导用户提供更多背景和细节，以帮助你更准确地回应。
        示例引导问题：
        
        用户提问示例：
        最近，在大模型技术领域，有一项非常热门的技术，名叫MCP，model context protocol，调用并深度总结，这项技术与OpenAI提出的function calling之间的区别。
        
        你应该给出的引导式回应示例：
        在比较MCP（Model Context Protocol）与OpenAI的Function Calling时，我可以涵盖以下几个方面：
        - 定义和基本概念：MCP和Function Calling的基本原理和目标。
        - 工作机制：它们如何处理模型的输入和输出。
        - 应用场景：它们分别适用于哪些具体场景？
        - 技术优势与局限性：各自的优劣势分析。
        - 生态和兼容性：它们是否能与现有的大模型和应用集成。
        - 未来发展趋势：这些技术未来的发展方向。
        请问你是否希望我特别关注某些方面，或者有特定的技术细节需要深入分析？
        
        再比如用户提问：
        请你帮我详细整理，华为910B2x鲲鹏920，如何部署DeepSeek模型。
        
        你应该给出的引导式回应示例：
        请提供以下详细信息，以便我能为您整理完整的部署指南：
        1. 您希望部署的DeepSeek模型具体是哪一个？（例如DeepSeek-VL、DeepSeek-Coder等）
        2. 目标系统环境（操作系统、已有软件环境等）？
        3. 是否有特定的深度学习框架要求？（如PyTorch、TensorFlow）
        4. 是否需要优化部署（如使用昇腾NPU加速）？
        5. 期望的使用场景？（如推理、训练、微调等）
        请提供这些信息后，我将为您整理具体的部署步骤。
        
        记住，保持友好而专业的态度，主动帮助用户明确需求，而不是直接给出不够精准的回答。现在用户提出问题如下：{}，请按照要求进行回复。
        """
        self.prompt_style2 = """
        你是一位知识广博、擅长利用多种外部工具的资深研究员。当用户已明确提出具体需求：{}，现在你的任务是：
        首先明确用户问题的核心及相关细节。
        尽可能调用可用的外部工具（例如：联网搜索工具get_answer、GitHub搜索工具get_answer_github、本地代码运行工具python_inter以及其他工具），围绕用户给出的原始问题和补充细节，进行广泛而深入的信息收集。
        综合利用你从各种工具中获取的信息，提供详细、全面、专业且具有深度的解答。你的回答应尽量达到2000字以上，内容严谨准确且富有洞察力。
        
        示例流程：
        用户明确需求示例：
        我目前正在学习 ModelContextProtocol（MCP），主要关注它在AI模型开发领域中的具体应用场景、技术细节和一些业界最新的进展。
        你的回应流程示例：
        首先重述并确认用户的具体需求。
        明确你将调用哪些外部工具，例如：
        使用联网搜索工具查询官方或权威文档对 MCP 在AI模型开发领域的具体应用说明；
        调用GitHub搜索工具，寻找业界针对MCP技术项目；
        整理并分析通过工具获取的信息，形成一篇逻辑清晰、结构合理的深度报告。
        
        再比如用户需要编写数据分析报告示例：
        我想针对某电信公司过去一年的用户数据，编写一份详细的用户流失预测数据分析报告，报告需要包括用户流失趋势分析、流失用户特征分析、影响用户流失的关键因素分析，并给出未来减少用户流失的策略建议。
        你的回应流程示例：
        明确并确认用户需求，指出分析内容包括用户流失趋势、流失用户特征、关键影响因素以及策略建议。
        明确你将调用哪些外部工具，例如：
        使用数据分析工具对提供的用户数据进行流失趋势分析，生成趋势图表；
        使用代码执行环境（如调用python_inter工具）对流失用户进行特征分析，确定典型特征；
        通过统计分析工具识别影响用户流失的关键因素（如服务质量、价格敏感度、竞争对手促销），同时借助绘图工具（fig_inter）进行重要信息可视化展示；
        使用互联网检索工具检索行业内最新的客户保留策略与实践，提出有效的策略建议。
        
        记住，回答务必详细完整，字数至少在2000字以上，清晰展示你是如何运用各种外部工具进行深入研究并形成专业结论的。
        
        """
        self.tools = [self.sql_inter_tool, self.extract_data_tool, self.python_inter_tool, self.fig_inter_tool, self.get_answer_tool, self.get_answer_github_tool]
        if messages != None:
            self.messages = messages
        else:
            self.messages = [{
                "role": "system", 
                "content": "你是VastOcean，一名助手。"
            }]
        self.client = OpenAI(api_key=self.API_KEY, base_url=self.BASE_URL)
        # 实例化客户端
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
        self.openai_sdk_client = OpenAI(api_key=self.OPENAI_API_KEY,  base_url=self.OPENAI_BASE_URL)        
        # OpenAI 客户端
        self.openai_client = AsyncOpenAI(
            base_url=self.OPENAI_BASE_URL,
            api_key=self.OPENAI_API_KEY,
        )
        self.PLAN_PROMPT = (
            "You are a helpful research assistant. Given a query, come up with a set of web searches "
            "to perform to best answer the query. Output between 10 and 20 terms to query for."
        )
        set_default_openai_client(self.openai_client)
        set_tracing_disabled(True)
        self.planner_agent = Agent(
            name="PlannerAgent",
            instructions=self.PLAN_PROMPT,
            model="gpt-4.1",
            output_type=WebSearchPlan,
        )
        self.SEARCH_INSTRUCTIONS = (
            "You are a research assistant. Given a search term, you search the web for that term and "
            "produce a concise summary of the results. The summary must 2-3 paragraphs and less than 300 "
            "words. Capture the main points. Write succinctly, no need to have complete sentences or good "
            "grammar. This will be consumed by someone synthesizing a report, so its vital you capture the "
            "essence and ignore any fluff. Do not include any additional commentary other than the summary "
            "itself."
        )
        # 你是一名研究助理。给定一个搜索词，你需要在互联网上搜索该词，并生成一个简洁的总结，总结应包含2-3段文字，字数少于300字。捕捉主要要点，简洁明了，无需完整句子或良好语法。这将被用于合成报告，因此捕捉核心内容并忽略任何冗余信息至关重要。除了总结本身，不要添加任何额外评论。
        self.search_agent = Agent(
            name="Search agent",
            instructions=self.SEARCH_INSTRUCTIONS,
            tools=[WebSearchTool()],
            model_settings=ModelSettings(tool_choice="required"),
            model="gpt-4.1",
        )
        self.REPORT_PROMPT_1 = (
            "You are a senior researcher tasked with writing a cohesive report for a research query. "
            "You will be provided with the original query, and some initial research done by a research "
            "assistant.\n"
            "You should first come up with an outline for the report that describes the structure and "
            "flow of the report. Then, generate the report and return that as your final output.\n"
            "The final output should be in markdown format, and it should be lengthy and detailed. Aim "
            "for 5-10 pages of content, at least 1000 words."
        )
        self.REPORT_PROMPT_2= (
            "You are a senior researcher tasked with writing a cohesive report for a research query. "
            "You will be provided with the original query, and some initial research done by a research "
            "assistant.\n"
            "You should first come up with an outline for the report that describes the structure and "
            "flow of the report. Then, generate the report and return that as your final output.\n"
            "The final output should be in markdown format, and it should be lengthy and detailed. Aim "
            "for 10-20 pages of content, at least 1500 words."
            "最终结果请用中文输出。"
        )
        self.writer_agent = Agent(
            name="WriterAgent",
            instructions=self.REPORT_PROMPT_2,
            model="gpt-4.1",
            output_type=ReportData,
        )

        try:
            print("正在测试模型能否正常调用...")
            self.models = self.client.models.list()
            
            if self.models:
                print("▌ VastOcean初始化完成，欢迎使用！")
            else:
                print("模型无法调用，请检查网络环境或本地模型配置。")

        except Exception as e:
            print("初始化失败，可能是网络或配置错误。详细信息：", str(e))


    def python_inter(self, py_code : str, g='globals()') -> str:
        """
        专门用于执行python代码，并获取最终查询或处理结果。
        :param py_code: 字符串形式的Python代码，
        :param g: g，字符串形式变量，表示环境变量，无需设置，保持默认参数即可
        核心作用: 充当代码执行的"环境"或"命名空间" (Namespace)
        :return：代码运行的最终结果
        """    
        print("正在调用python_inter工具运行Python代码...")
        try:
            # 尝试如果是表达式，则返回表达式运行结果
            return str(eval(py_code, g))
        # 若报错，则先测试是否是对相同变量重复赋值
        except Exception as e:
            global_vars_before = set(g.keys())
            try:            
                exec(py_code, g)
            except Exception as e:
                return f"代码执行时报错{e}"
            global_vars_after = set(g.keys())
            new_vars = global_vars_after - global_vars_before
            # 若存在新变量
            if new_vars:
                result = {var: g[var] for var in new_vars}
                print("代码已顺利执行，正在进行结果梳理...")
                return str(result)
            else:
                print("代码已顺利执行，正在进行结果梳理...")
                return "已经顺利执行代码"

    def fig_inter(self, py_code, fname, g='globals()'):
        print("正在调用fig_inter工具运行Python代码...")
        import matplotlib
        # Explicitly use a non-interactive backend suitable for saving files
        # matplotlib.use('Agg') # Uncomment this line if you encounter backend issues
        import os
        import matplotlib.pyplot as plt
        import seaborn as sns
        import pandas as pd


        # 用于执行代码的本地变量
        local_vars = {"plt": plt, "pd": pd, "sns": sns}

        # 相对路径保存目录
        pics_dir = 'pics'
        if not os.path.exists(pics_dir):
            os.makedirs(pics_dir)

        try:
            # 执行用户代码
            exec(py_code, g, local_vars)
            # Update global environment if needed (optional, based on original logic)
            # g.update(local_vars) # Consider if this update is necessary outside IPython context

            # 获取图像对象
            # Try getting the figure from plt or local_vars
            fig = local_vars.get(fname, None)
            if fig is None and plt.gcf().get_axes(): # Check if there's an active figure managed by plt
                 fig = plt.gcf()

            if fig and fig.get_axes(): # Check if the figure actually contains something
                rel_path = os.path.join(pics_dir, f"{fname}.png")
                fig.savefig(rel_path, bbox_inches='tight')
                # display(Image(filename=rel_path)) # Removed for non-notebook environment
                plt.close(fig) # Close the figure to free memory
                print("代码已顺利执行，图像已保存。")
                return f"✅ 图片已成功保存至: {rel_path}"
            elif fname in local_vars and not isinstance(local_vars[fname], plt.Figure):
                 return f"⚠️ 代码执行成功，但变量 '{fname}' 不是一个有效的 Matplotlib Figure 对象。"
            else:
                # Check if plt was used directly without assigning to fname
                if plt.gcf().get_axes():
                     rel_path = os.path.join(pics_dir, f"{fname}.png")
                     plt.savefig(rel_path, bbox_inches='tight')
                     plt.close(plt.gcf()) # Close the figure
                     print("代码已顺利执行，使用 plt 直接生成的图像已保存。")
                     return f"✅ 图片已成功保存至: {rel_path} (通过 plt 直接保存)"
                else:
                    return "⚠️ 代码执行成功，但未找到有效的图像对象或绘图内容。请确保代码生成了图像并赋值给变量 '{fname}' 或使用了 plt。"

        except Exception as e:
            # Ensure any open figures are closed on error too
            plt.close('all')
            return f"❌ 执行失败：{e}"
        # finally:
            # matplotlib.use(current_backend) # Removed for non-notebook environment

    def sql_inter(self,sql_query, g='globals()'):
        """
        用于执行一段SQL代码，并最终获取SQL代码执行结果，\
        核心功能是将输入的SQL代码传输至MySQL环境中进行运行，\
        并最终返回SQL代码运行结果。需要注意的是，本函数是借助pymysql来连接MySQL数据库。
        :param sql_query: 字符串形式的SQL查询语句，用于执行对MySQL中telco_db数据库中各张表进行查询，并获得各表中的各类相关信息
        :param g: g，字符串形式变量，表示环境变量，无需设置，保持默认参数即可
        :return：sql_query在MySQL中的运行结果。
        """
        print("正在调用sql_inter工具运行SQL代码...")

        connection = pymysql.connect(
            host = self.host,  
            user = self.user, 
            passwd = self.mysql_pw,  
            db = self.db,
            port = int(self.port),
            charset='utf8',
        )
        
        try:
            with connection.cursor() as cursor:
                sql = sql_query
                cursor.execute(sql)
                results = cursor.fetchall()
                print("SQL代码已顺利运行，正在整理答案...")

        finally:
            connection.close()

        return json.dumps(results)

    def extract_data(self,sql_query, df_name, g='globals()'):
        """
        借助pymysql将MySQL数据库中的某张表读取并保存到本地Python环境中。
        :param sql_query: 字符串形式的SQL查询语句，用于提取MySQL中的某张表。
        :param df_name: 将MySQL数据库中提取的表格进行本地保存时的变量名，以字符串形式表示。
        :param g: g，字符串形式变量，表示环境变量，无需设置，保持默认参数即可
        :return：表格读取和保存结果
        """
        print("正在调用extract_data工具运行SQL代码...")
        
        connection = pymysql.connect(
            host = self.host,  
            user = self.user, 
            passwd = self.mysql_pw,  
            db = self.db,
            port = int(self.port),
            charset='utf8',
        )
        
        print("正在连接数据库...")
        print(f"数据库连接成功: {connection}")

        try:
            g[df_name] = pd.read_sql(sql_query, connection)
            print("代码已顺利执行，正在进行结果梳理...")
            return f"✅ 数据已成功保存至: {df_name}"
        except Exception as e:
            print(f"extract_data执行出错: {e}")
            return f"❌ 执行失败: {e}"
        finally:
            print("正在关闭数据库连接...")
            if 'connection' in locals() and connection:
                connection.close()
    
    def google_search(self,query, num_results=10, site_url=None):
        
        url = "https://www.googleapis.com/customsearch/v1"

        # API 请求参数
        if site_url == None:
            params = {
            'q': query,          
            'key': self.google_search_key,      
            'cx': self.cse_id,        
            'num': num_results   
            }
        else:
            params = {
            'q': query,         
            'key': self.google_search_key,      
            'cx': self.cse_id,        
            'num': num_results,  
            'siteSearch': site_url
            }

        # 发送请求
        response = requests.get(url, params=params)
        response.raise_for_status()

        # 解析响应
        search_results = response.json().get('items', [])

        # 提取所需信息
        results = [{
            'title': item['title'],
            'link': item['link'],
            'snippet': item['snippet']
        } for item in search_results]

        return results

    def process_bocha_results(self,search_results, include_images=True):
        """处理博查搜索API的返回结果，提取标题、链接、摘要以及图片信息
        
        :param search_results: 博查搜索API返回的JSON结果
        :param include_images: 是否包含图片信息，默认为True
        :return: 提取后的结果字典，包含网页结果和图片结果
        """
        processed_results = {
            'web_results': [],
            'image_results': []
        }
        
        # 检查是否有有效数据
        if not search_results or 'data' not in search_results:
            print("搜索结果为空或格式不正确")
            return processed_results
        
        # 从结果中提取网页信息
        data = search_results.get('data', {})
        web_pages = data.get('webPages', {})
        web_results_list = web_pages.get('value', [])
        
        # 提取每个网页结果的title, link和snippet
        for item in web_results_list:
            processed_results['web_results'].append({
                'title': item.get('name', '无标题'),
                'link': item.get('url', '无链接'),
                'snippet': item.get('snippet', '无摘要'),
                'summary': item.get('summary', '无总结')
            })
        
        # 如果需要提取图片信息
        if include_images and 'images' in data and data['images'] and 'value' in data['images']:
            image_results_list = data['images']['value']
            
            # 提取每个图片结果的信息
            for item in image_results_list:
                image_info = {
                    'thumbnailUrl': item.get('thumbnailUrl', '无缩略图链接'),
                    'contentUrl': item.get('contentUrl', '无图片链接'),
                    'hostPageUrl': item.get('hostPageUrl', '无来源页面链接'),
                    'width': item.get('width', 0),
                    'height': item.get('height', 0)
                }
                processed_results['image_results'].append(image_info)
        
        return processed_results
    def bocha_search(self,query, num_results=5, include_images=True):
        """使用Bocha API进行搜索，并返回处理后的结果
        
        :param query: 搜索查询字符串
        :param num_results: 返回结果的数量
        :param include_images: 是否包含图片结果
        :return: 处理后的搜索结果字典
        """
        import requests
        import json
        if not self.bocha_web_search_api:
            print("错误：BOCHA_WEB_SEARCH_API环境变量未设置")
            return {'web_results': [], 'image_results': []}
        
        url = "https://api.bochaai.com/v1/web-search"
        
        payload = json.dumps({
            "query": query,
            "summary": True,
            "freshness": "noLimit",
            "count": num_results,
            "page": 1
        })
        
        headers = {
            'Authorization': 'Bearer '+self.bocha_web_search_api,
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.request("POST", url, headers=headers, data=payload)
            response.raise_for_status()
            raw_results = response.json()
            
            # 处理并提取结果
            processed_results = self.process_bocha_results(raw_results, include_images)
            
            # 打印网页搜索结果摘要
            web_results = processed_results['web_results']
            print(f"找到 {len(web_results)} 条关于 '{query}' 的网页搜索结果:")
            for i, result in enumerate(web_results, 1):
                print(f"\n--- 网页结果 {i} ---")
                print(f"标题: {result['title']}")
                print(f"链接: {result['link']}")
                print(f"摘要: {result['snippet'][:150]}...")
                print(f"总结: {result['summary'][:150]}...")
            
            # 打印图片搜索结果摘要
            image_results = processed_results['image_results']
            if include_images:
                print(f"\n找到 {len(image_results)} 张相关图片:")
                for i, img in enumerate(image_results, 1):
                    print(f"\n--- 图片 {i} ---")
                    print(f"图片链接: {img['contentUrl']}")
                    print(f"图片尺寸: {img['width']}x{img['height']}")
                    print(f"来源页面: {img['hostPageUrl']}")
            
            return processed_results
            
        except Exception as e:
            print(f"搜索过程中发生错误: {e}")
            return {'web_results': [], 'image_results': []}
        
    # 下载并显示图片的示例代码
    def download_search_images(self, query, image_results, base_dir='./search_images', max_images=15):
        """下载并保存 Bocha 搜索结果中的图片。

        :param query: 原始搜索查询，用于创建子目录。
        :param image_results: 包含图片信息的列表，来自 process_bocha_results。
        :param base_dir: 保存图片文件的根目录。
        :param max_images: 最多下载几张图片。
        """
        import requests
        import os

        if not image_results:
            print("没有图片结果可供下载。")
            return

        # 创建保存目录
        query_dir_name = self.windows_compatible_name(query)
        save_dir = os.path.join(base_dir, query_dir_name)
        os.makedirs(save_dir, exist_ok=True)

        # Determine the effective number of images to download
        effective_max_images = min(max_images, len(image_results))

        print(f"开始下载 '{query}' 的图片 (最多 {effective_max_images} 张) 到 '{save_dir}'...")

        download_count = 0
        # Loop up to the effective maximum number of images
        for i, img in enumerate(image_results[:effective_max_images], 1):
            try:
                content_url = img.get('contentUrl')
                if not content_url:
                    print(f"  - 图片 {i} 缺少 'contentUrl'，跳过。")
                    continue

                # 尝试从 URL 获取文件名和扩展名
                try:
                    file_name_from_url = os.path.basename(requests.utils.urlparse(content_url).path)
                    # 基本的文件名清理和扩展名提取
                    base, ext = os.path.splitext(file_name_from_url)
                    if not ext or len(ext) > 5: # 如果没有扩展名或扩展名太长，可能不是有效的图片扩展名
                        # 尝试从 Content-Type 获取 (这需要发送 HEAD 请求，可能较慢，暂时省略)
                        # 默认使用 .jpg 或基于已知类型
                         content_type_guess = requests.head(content_url, timeout=5).headers.get('Content-Type', '').lower()
                         if 'jpeg' in content_type_guess or 'jpg' in content_type_guess:
                             ext = '.jpg'
                         elif 'png' in content_type_guess:
                             ext = '.png'
                         elif 'gif' in content_type_guess:
                             ext = '.gif'
                         elif 'webp' in content_type_guess:
                             ext = '.webp'
                         else:
                            ext = '.jpg' # Default extension
                except Exception:
                    ext = '.jpg' # Fallback extension

                # 构建文件名和完整路径
                filename = f"image_{i:02d}{ext}"
                filepath = os.path.join(save_dir, filename)

                # 下载图片
                print(f"  - 下载图片 {i} 从 {content_url} ...", end='')
                response = requests.get(content_url, stream=True, timeout=10) # Added timeout
                response.raise_for_status()

                # 保存图片
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                print(f" -> 已保存为 {filename}")
                download_count += 1

            except requests.exceptions.RequestException as e:
                print(f" -> 下载失败 (网络或请求错误): {e}")
            except IOError as e:
                print(f" -> 保存失败 (文件写入错误): {e}")
            except Exception as e:
                print(f" -> 发生未知错误: {e}")
        
        print(f"图片下载完成，共成功下载 {download_count} 张。")

    def windows_compatible_name(self,s, max_length=255):
        """
        将字符串转化为符合Windows文件/文件夹命名规范的名称。
        
        参数:
        - s (str): 输入的字符串。
        - max_length (int): 输出字符串的最大长度，默认为255。
        
        返回:
        - str: 一个可以安全用作Windows文件/文件夹名称的字符串。
        """

        # Windows文件/文件夹名称中不允许的字符列表
        forbidden_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']

        # 使用下划线替换不允许的字符
        for char in forbidden_chars:
            s = s.replace(char, '_')

        # 删除尾部的空格或点
        s = s.rstrip(' .')

        # 检查是否存在以下不允许被用于文档名称的关键词，如果有的话则替换为下划线
        reserved_names = ["CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", 
                        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"]
        if s.upper() in reserved_names:
            s += '_'

        # 如果字符串过长，进行截断
        if len(s) > max_length:
            s = s[:max_length]

        return s
    
    def calculate_tokens(self,text):
        '''计算给定文本的 token 数量'''
        # 计算 tokens，免费
        try:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo") # 或者你使用的模型
            return len(encoding.encode(text))
        except Exception as e:
            print(f"警告：使用 tiktoken 计算 tokens 时出错: {e}. 返回 0。")
            return 0
        
    def save_single_bocha_result(self,result_item, query, base_dir='./auto_search'):
        """
        处理单个博查搜索结果项，并将其保存为 JSON 文件。

        :param result_item: 从 process_bocha_results 返回的列表中的单个字典项。
                            期望包含 'title', 'link', 'summary', 'snippet'。
        :param query: 原始的搜索查询字符串，用于创建目录。
        :param base_dir: 保存文件的根目录。
        :return: 保存成功则返回清理后的文件名 (不含扩展名)，否则返回 None。
        """
        try:
            # 提取信息
            title = result_item.get('title', '无标题')
            link = result_item.get('link', '无链接')
            # 优先使用 summary，如果为空则使用 snippet
            content = result_item.get('summary') or result_item.get('snippet', '无内容')
            
            # 清理文件名
            clean_title = self.windows_compatible_name(title)
            if not clean_title: # 如果清理后标题为空，则跳过
                print(f"警告：结果 '{title}' 清理后标题为空，跳过保存。")
                return None

            tokens = self.calculate_tokens(content)
                
            # 准备 JSON 数据
            json_data = [{
                "link": link,
                "title": clean_title, # 使用清理后的标题
                "content": content,
                "tokens": tokens
            }]
            
            # 创建目录 (使用清理后的查询作为目录名的一部分，确保目录名也合法)
            query_dir_name = self.windows_compatible_name(query)
            dir_path = os.path.join(base_dir, query_dir_name)
            os.makedirs(dir_path, exist_ok=True)
            
            # 构建文件路径
            file_path = os.path.join(dir_path, f"{clean_title}.json")
            
            # 保存 JSON 文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
                
            print(f"结果已保存到: {file_path}")
            return clean_title

        except Exception as e:
            print(f"处理和保存结果 '{result_item.get('title', '未知标题')}' 时出错: {e}")
            return None
  
    def get_search_result(self,q):
        """
        当你无法回答某个问题时，调用该函数，能够获得答案,使用 Bocha 搜索获取信息，并聚合结果内容直到达到 token 上限。
        :param q: 必选参数，询问的问题，字符串类型对象
        :return：某问题的答案，以字符串形式呈现
        """
        print(f"正在为问题 '{q}' 执行 Bocha 搜索...")
        # 调用 bocha_search，这里我们可能不需要图片结果
        # 注意：确保你的 bocha_search 函数返回包含 'web_results' 的字典
        results_data = self.bocha_search(query=q, num_results=10, include_images=True) 
        if not results_data or not results_data.get('web_results'):
            print("未能获取到有效的网页搜索结果。")
            return "" # 返回空字符串或进行其他错误处理
        
        print(f"\n开始保存 '{q}' 的搜索结果...")
        saved_count = 0
        for item in results_data['web_results']:
            saved_title = self.save_single_bocha_result(item, q)
            if saved_title:
                saved_count += 1
                print(f"\n共保存了 {saved_count} 个结果文件。")
            else:
                print("没有获取到有效的网页搜索结果来保存。")

        if results_data['image_results']:
            self.download_search_images(q, results_data['image_results'])
        
        num_tokens = 0
        aggregated_content = ""
        web_results = results_data['web_results']

        print(f"获取到 {len(web_results)} 条网页结果，开始聚合内容 (上限 {self.MAX_TOKENS_LIMIT} tokens)...")
        
        for i, item in enumerate(web_results):
            # 优先使用 summary，如果为空则使用 snippet
            content_piece = item.get('summary') or item.get('snippet')
            
            if not content_piece: # 如果内容为空，跳过此条结果
                print(f"  - 结果 {i+1} ('{item.get('title', '无标题')}') 内容为空，跳过。")
                continue

            # 计算这段内容的 tokens
            current_tokens = self.calculate_tokens(content_piece)
            
            # 检查是否会超过上限
            if num_tokens + current_tokens <= self.MAX_TOKENS_LIMIT:
                # 追加内容和分隔符（例如换行符）
                aggregated_content += content_piece + "\n\n" # 使用两个换行符分隔不同结果
                num_tokens += current_tokens
                print(f"  + 添加结果 {i+1} ('{item.get('title', '无标题')}'): {current_tokens} tokens (累计 {num_tokens} tokens)")
            else:
                print(f"  ! 结果 {i+1} ('{item.get('title', '无标题')}') ({current_tokens} tokens) 将超出上限，停止聚合。")
                break # 停止添加内容

        print(f"内容聚合完成，总计 tokens: {num_tokens}")
        return aggregated_content
    
    def get_github_readme(self,dic):

        owner = dic['owner']
        repo = dic['repo']

        headers = {
            "Authorization": self.github_token,
            "User-Agent": self.search_user_agent
        }

        response = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=headers)

        readme_data = response.json()
        encoded_content = readme_data.get('content', '')
        decoded_content = base64.b64decode(encoded_content).decode('utf-8')
        
        return decoded_content
    
    def extract_github_repos(self,search_results):
        # 使用列表推导式筛选出项目主页链接
        repo_links = [result['link'] for result in search_results if '/issues/' not in result['link'] and '/blob/' not in result['link'] and 'github.com' in result['link'] and len(result['link'].split('/')) == 5]

        # 从筛选后的链接中提取owner和repo
        repos_info = [{'owner': link.split('/')[3], 'repo': link.split('/')[4]} for link in repo_links]

        return repos_info
    
    def get_search_text_github(self,q,dic):
        
        title = dic['owner'] + '_' + dic['repo']
        title = self.windows_compatible_name(title)

        # 创建问题答案正文
        text = self.get_github_readme(dic)

        # 写入本地json文件
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")     
        json_data = [
            {
                "title": title,
                "content": text,
                "tokens": len(encoding.encode(text))
            }
        ]
        
        # 自动创建目录，如果不存在的话
        dir_path = f'./auto_search/{q}'
        os.makedirs(dir_path, exist_ok=True)
        
        with open('./auto_search/%s/%s.json' % (q, title), 'w') as f:
            json.dump(json_data, f)

        return title
    
    def get_answer(self,q, g='globals()'):
        """
        当你无法回答某个问题时，调用该函数，能够获得答案
        :param q: 必选参数，询问的问题，字符串类型对象
        :param g: g，字符串形式变量，表示环境变量，无需设置，保持默认参数即可
        :return：某问题的答案，以字符串形式呈现
        """
        # 默认搜索返回5个答案
        print('正在接入博查搜索，查找和问题相关的答案...')
        
        return self.get_search_result(q)
    
    def get_answer_github(self,q, g='globals()'):
        """
        当你无法回答某个问题时，调用该函数，能够获得答案
        :param q: 必选参数，询问的问题，字符串类型对象
        :param g: g，字符串形式变量，表示环境变量，无需设置，保持默认参数即可
        :return：某问题的答案，以字符串形式呈现
        """
        
        # 默认搜索返回5个答案
        print('正在接入谷歌搜索，查找和问题相关的答案...')
        search_results = self.google_search(query=q, num_results=5, site_url='https://github.com/')
        results = self.extract_github_repos(search_results)
        
        # 创建对应问题的子文件夹
        folder_path = './auto_search/%s' % q
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        print('正在读取相关项目说明文档...')
        num_tokens = 0
        content = ''
        
        for dic in results:
            title = self.get_search_text_github(q, dic)
            with open('./auto_search/%s/%s.json' % (q, title), 'r') as f:
                jd = json.load(f)
            num_tokens += jd[0]['tokens']
            if num_tokens <= self.MAX_TOKENS_LIMIT:
                content += jd[0]['content']
            else:
                break
        print('正在进行最后的整理...')
        return(content)
    
    def print_code_if_exists(self,function_args):
        """
        如果存在代码片段，则打印代码
        """
        def convert_to_markdown(code, language):
            return f"```{language}\n{code}\n```"
        
        # 如果是SQL，则按照Markdown中SQL格式打印代码
        if function_args.get('sql_query'):
            code = function_args['sql_query']
            markdown_code = convert_to_markdown(code, 'sql')
            print("即将执行以下代码：")
            print(markdown_code)

        # 如果是Python，则按照Markdown中Python格式打印代码
        elif function_args.get('py_code'):
            code = function_args['py_code']
            markdown_code = convert_to_markdown(code, 'python')
            print("即将执行以下代码：")
            print(markdown_code)

    def create_function_response_messages(self,messages, response):
    
        """
        调用外部工具，并更新消息列表
        :param messages: 原始消息列表
        :param response: 模型某次包含外部工具调用请求的响应结果
        :return：messages，追加了外部工具运行结果后的消息列表
        """

        available_functions = {
            "python_inter": self.python_inter,
            "fig_inter": self.fig_inter,
            "sql_inter": self.sql_inter,
            "extract_data": self.extract_data,
            "get_answer": self.get_answer,
            "get_answer_github": self.get_answer_github,
        }
        
        # 提取function call messages
        function_call_messages = response.choices[0].message.tool_calls

        # 将function call messages追加到消息列表中
        messages.append(response.choices[0].message.model_dump())

        # 提取本次外部函数调用的每个任务请求
        for function_call_message in function_call_messages:
            
            # 提取外部函数名称
            tool_name = function_call_message.function.name
            # 提取外部函数参数
            tool_args = json.loads(function_call_message.function.arguments)       
            
            # 查找外部函数
            fuction_to_call = available_functions[tool_name]

            # 打印代码
            self.print_code_if_exists(function_args=tool_args)

            # 运行外部函数
            try:
                tool_args['g'] = globals()
                print(f"[调试] 正在执行工具 {tool_name} 参数: {tool_args}")
                function_response = fuction_to_call(**tool_args)
                print(f"[调试] 工具执行结果: {function_response[:100]}...")
            except Exception as e:
                error_msg = f"函数运行报错如下: {e}"
                function_response = error_msg
                print(f"[错误] {error_msg}")

            # 拼接消息队列
            messages.append(
                {
                    "role": "tool",
                    "content": function_response,
                    "tool_call_id": function_call_message.id,
                }
            )
            
        return messages     
    
    def chat_base(self, messages, client, model):
        """获得一次模型对用户的响应。"""
        
        # 检查最后一条用户消息中是否包含数据库关键词
        last_user_msg = None
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break
        
        if last_user_msg:
            print(f"[调试] 最后的用户消息: {last_user_msg}")
            db_keywords = ["数据库", "表", "添加数据", "插入", "创建表"]
            detected_keywords = [kw for kw in db_keywords if kw in last_user_msg]
            if detected_keywords:
                print(f"[调试] 检测到数据库关键词: {detected_keywords}")
        
        try:
            print("[调试] 发送请求给API...")
            response = client.chat.completions.create(
                model=model,  
                messages=messages,
                tools=self.tools,
            )
            print(f"[调试] 收到响应，finish_reason: {response.choices[0].finish_reason}")
            
            # 如果没有调用工具但最后的消息包含数据库关键词，尝试打印模型的思考
            if response.choices[0].finish_reason != "tool_calls" and detected_keywords:
                print(f"[警告] 检测到数据库相关关键词但模型没有调用工具! 模型返回: {response.choices[0].message.content[:100]}...")
            
        except Exception as e:
            print("模型调用报错" + str(e))
            return None

        if response.choices[0].finish_reason == "tool_calls":
            print(f"[调试] 模型决定调用工具: {[t.function.name for t in response.choices[0].message.tool_calls]}")
            while True:
                messages = self.create_function_response_messages(messages, response)
                response = client.chat.completions.create(
                    model=model,  
                    messages=messages,
                    tools=self.tools,
                )
                if response.choices[0].finish_reason != "tool_calls":
                    break
        
        return response

    def save_markdown_to_file(self,content: str, filename_hint: str, directory="research_task"):
        # 在当前项目目录下创建 research_task 文件夹
        save_dir = os.path.join(os.getcwd(), directory)

        # 如果目录不存在则创建
        os.makedirs(save_dir, exist_ok=True)

        # 创建文件名（取前8个字符并加上...）
        filename = f"{filename_hint[:8]}....md"

        # 完整文件路径
        file_path = os.path.join(save_dir, filename)

        # 将内容保存为Markdown文档
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)

        print(f"文件已成功保存到：{file_path}")

    def chat(self):
        print("你好，我是周浩洋制作的`VastOcean`，有什么需要帮助的？")
        while True:
            question = input("请输入您的问题(输入退出以结束对话): ")
            if question == "退出":
                break  
            print(f"[调试] 当前消息队列长度: {len(self.messages)}")
            self.messages.append({"role": "user", "content": question})
            self.messages = self.messages[-20: ]
            
            response = self.chat_base(messages=self.messages, 
                                 client=self.client, 
                                 model=self.MODEL)
            
            # 添加对response为None的检查
            if response is None:
                print("***`VastOcean:`*** 连接错误，请稍后重试或检查网络连接")
                continue
            
            print("***`VastOcean:`***" + response.choices[0].message.content)
            self.messages.append(response.choices[0].message)
            
    def research_task_simple(self, question):
        """
        简单研究任务
        """
        response = self.client.chat.completions.create(model=self.MODEL,
                                                  messages=[{"role": "user", "content": self.prompt_style1.format(question)}])
        
        print("***`VastOcean:`***" + response.choices[0].message.content)

        new_messages = [
            {"role": "user", "content": question},
            response.choices[0].message.model_dump()
        ]
        
        new_question = input("请输入您的补充说明(输入退出以结束对话): ")
        if new_question == "退出":
            return None
        else:
            new_messages.append({"role": "user", "content":self.prompt_style2.format(new_question)})
            
            second_response = self.chat_base(messages=new_messages, 
                                        client=self.client, 
                                        model=self.MODEL)
            
            print("***`VastOcean:`***" + second_response.choices[0].message.content)
            
            self.save_markdown_to_file(content=second_response.choices[0].message.content, 
                                  filename_hint=question)
            
    async def research_task_deep(self, query:str):
        """
        深度研究任务
        """
        # Indicate that the research process is starting
        print("***`VastOcean:`***" +"Starting research...")
        # Step 1: Generate search plan using planner_agent
        search_plan = await self.plan_searches(query)
        # Step 2: Perform the searches using search_agent
        search_results = await self.perform_searches(search_plan)
        # Step 3: Write the final report using writer_agent
        report = await self.write_report(query, search_results)

        # Final printed report
        print("\n\n=====REPORT=====\n\n")
        print(report.markdown_report)
        print("\n\n=====FOLLOW UP QUESTIONS=====\n\n")
        follow_up_questions = "\n".join(report.follow_up_questions)
        print(follow_up_questions)
         # 保存为 Markdown 文件
        self.save_report_as_md(query, report.markdown_report)
    
    async def plan_searches(self, query: str) -> WebSearchPlan:
        print("Planning searches...")
        result = await Runner.run(
            self.planner_agent,
            f"Query: {query}",
        )
        return result.final_output_as(WebSearchPlan)
    async def perform_searches(self, search_plan: WebSearchPlan) -> list[str]:
        print("Starting searching...")
        num_completed = 0
        tasks = [asyncio.create_task(self.search(item)) for item in search_plan.searches]
        results = []
        for task in asyncio.as_completed(tasks):
            result = await task
            if result is not None:
                results.append(result)
            num_completed += 1
            print(f"Searching... {num_completed}/{len(tasks)} completed")
        return results
    async def search(self, item: WebSearchItem) -> str | None:
        print(f"Search term: {item.query}\nReason for searching: {item.reason}")
        try:
            result = await Runner.run(
                self.search_agent,
                input=f"Search term: {item.query}\nReason for searching: {item.reason}"
            )
            return str(result.final_output)
        except Exception:
            return None
    async def write_report(self, query: str, search_results: list[str]) -> ReportData:
        print("Thinking about report...")
        print(f"Original query: {query}\nSummarized search results: {search_results}")
        
        # Use run instead of run_streamed to avoid async context issues
        result = await Runner.run(
            self.writer_agent,
            input=f"Original query: {query}\nSummarized search results: {search_results}",
        )
        # 用于在生成报告时显示进度的消息列表
        update_messages = [
            "Thinking about report...",
            "Planning report structure...",
            "Writing outline...",
            "Creating sections...",
            "Cleaning up formatting...",
            "Finalizing report...",
            "Finishing report...",
        ]

        last_update = time.time() # 记录上次更新消息的时间
        next_message = 0# 下一个要显示的消息索引
        for _ in result.new_items:# 迭代代理运行产生的新项目（可能是中间步骤或状态）
            # 如果距离上次更新超过5秒，并且还有未显示的消息
            if time.time() - last_update > 5 and next_message < len(update_messages):
                print(update_messages[next_message])
                next_message += 1
                last_update = time.time()
        # 返回最终的报告数据
        return result.final_output_as(ReportData)
    def save_report_as_md(self, query: str, markdown_content: str) -> None:
        """
        保存生成的报告为 Markdown 文件
        """
        # 创建文件夹（如果不存在）
        folder_name = "research_reports"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        # 使用用户的查询作为文件名
        sanitized_query = query.replace(" ", "_").replace("：", "").replace("?", "")
        file_name = f"{folder_name}/关于{sanitized_query}调研报告.md"

        # 写入 Markdown 文件
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(markdown_content)

        print(f"Report saved as: {file_name}")
    def clear_messages(self):
        self.messages = []

def main():
    while True:
        vastOcean = VastOcean()
        os.system('cls')
        print("欢迎来到周浩洋's VastOcean!")
        print("请选择功能(输入数字1/2/3/4):")
        print("1.chat with tools")
        print("2.deep research(bocha version)")    
        print("3.deep research(openai version)")
        print("4.exit")
        char = input()
        if char == '1':
            vastOcean.chat()
        elif char == '2':
            question = input("请输入你要深度研究的任务:")
            vastOcean.research_task_simple(question)
        elif char == '3':
            question = input("请输入你要深度研究的任务:")
            # Use asyncio.run() to execute the async function
            try:
                asyncio.run(vastOcean.research_task_deep(question))
            except Exception as e:
                print(f"深度研究任务执行出错: {e}") # Add error handling
        elif char == '4':
            print("安全退出！")
            break
        else:
            print("输入格式不合法，请重新输入！")
            os.system('cls')
    
if __name__=='__main__':  # 这里应该是双下划线__main__，而不是main
    main()

