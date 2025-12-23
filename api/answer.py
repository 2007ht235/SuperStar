import openai
import time
import json
import logging
from configparser import ConfigParser

# 初始化日志配置
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DoubaoTiku:
    def __init__(self, conf_path="config.ini"):
        """初始化：加载配置并设置OpenAI客户端"""
        self._conf = self._load_config(conf_path)
        self.last_request_time = None
        self._init_client()
        # 加载业务逻辑配置（保留原有网课答题的参数）
        self._load_business_config()

    def _load_config(self, conf_path):
        """加载config.ini配置文件"""
        conf = ConfigParser()
        if not conf.read(conf_path, encoding='utf-8'):
            raise FileNotFoundError(f"配置文件 {conf_path} 不存在或读取失败")
        return conf

    def _init_client(self):
        """初始化OpenAI兼容客户端（适配你的config.ini字段名）"""
        # 从配置文件读取边缘网关核心参数（匹配你的config.ini字段）
        self.api_key = self._conf.get('tiku', 'doubao_api_key')
        self.base_url = self._conf.get('tiku', 'doubao_endpoint', fallback='https://ai-gateway.vei.volces.com/v1')
        self.model = self._conf.get('tiku', 'doubao_model', fallback='doubao-seed-1.6')
        self.min_interval = int(self._conf.get('tiku', 'doubao_min_interval', fallback=1))
        self.max_tokens = 1024  # 固定Token数，也可在config.ini新增配置项读取

        # 校验必填API Key
        if not self.api_key:
            raise ValueError("请在config.ini的[tiku]节点配置doubao_api_key（边缘网关API Key）")

        # 初始化OpenAI客户端
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _load_business_config(self):
        """加载网课答题的业务逻辑配置（保留原有参数）"""
        self.submit = self._conf.getboolean('tiku', 'submit', fallback=True)
        self.cover_rate = float(self._conf.get('tiku', 'cover_rate', fallback=0.8))
        # 读取判断题选项映射
        self.true_list = [item.strip() for item in self._conf.get('tiku', 'true_list', fallback='正确,对,√,是').split(',')]
        self.false_list = [item.strip() for item in self._conf.get('tiku', 'false_list', fallback='错误,×,否,不对,不正确').split(',')]
        logger.debug("业务配置加载完成：submit=%s, cover_rate=%.1f", self.submit, self.cover_rate)

    def _clean_response(self, content):
        """清洗模型返回内容，确保JSON格式正确"""
        return content.strip().replace('```json', '').replace('```', '')

    def answer_question(self, full_question, image_url=None):
        """
        调用边缘网关答题（支持纯文本/图文问答）
        :param full_question: 问题文本
        :param image_url: 图片URL（多模态时传入，默认None为纯文本）
        :return: 拼接后的答案字符串
        """
        # 1. 系统提示词（保持题库答题逻辑）
        system_prompt = "本题为简答题，直接给出核心答案，以JSON格式返回：{\"Answer\": [\"答案内容\"]}。禁止输出任何多余解释、MD语法或参考资料。"

        # 2. 控制请求频率，避免超限
        if self.last_request_time:
            interval = time.time() - self.last_request_time
            if interval < self.min_interval:
                sleep_time = self.min_interval - interval
                logger.debug(f"请求间隔过短，等待 {sleep_time:.2f} 秒")
                time.sleep(sleep_time)
        self.last_request_time = time.time()

        # 3. 构造消息体（支持纯文本/多模态）
        messages = [{"role": "system", "content": system_prompt}]
        user_content = []
        
        # 纯文本问题
        user_content.append({"type": "text", "text": full_question})
        # 多模态：添加图片URL（如有）
        if image_url:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

        messages.append({"role": "user", "content": user_content})

        # 4. 调用边缘网关API
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # 低随机性保证答案稳定
                max_tokens=self.max_tokens,
                stream=False       # 非流式输出
            )

            # 5. 解析返回结果
            content = completion.choices[0].message.content
            cleaned_content = self._clean_response(content)
            answer_json = json.loads(cleaned_content)
            answer_list = answer_json.get('Answer', [])

            if not answer_list:
                logger.error("边缘网关返回的答案为空")
                return None

            final_answer = "\n".join(answer_list).strip()
            # 若配置了自动提交，可在此处添加提交逻辑（根据你的业务需求扩展）
            if self.submit:
                logger.debug(f"自动提交答案：{final_answer}")

            return final_answer

        except Exception as e:
            logger.error(f"答题失败：{str(e)}")
            return None

# -------------------------- 测试示例 --------------------------
if __name__ == "__main__":
    # 初始化题库对象
    try:
        tiku = DoubaoTiku(conf_path="config.ini")
        
        # 测试纯文本问答（替换为你的题库问题）
        test_question = "请简述边缘大模型网关的核心作用"
        test_answer = tiku.answer_question(test_question)
        print(f"问题：{test_question}\n答案：{test_answer}\n")

        # 测试多模态图文问答（需替换为有效图片URL）
        # img_question = "描述这张图片的内容"
        # img_url = "https://example.com/your-image.jpg"
        # img_answer = tiku.answer_question(img_question, image_url=img_url)
        # print(f"图文问题：{img_question}\n答案：{img_answer}")

    except Exception as e:
        logger.error(f"初始化失败：{str(e)}")
