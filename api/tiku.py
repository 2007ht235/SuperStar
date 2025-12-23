# 在DoubaoTiku类中新增
def query(self, q):
    """适配base.py的query方法，传入题目字典返回答案"""
    return self.answer_question(q["title"])

def get_submit_params(self):
    """适配提交参数逻辑"""
    return "1" if not self.submit else ""

# 新增属性（在_init_client后）
self.DISABLE = False  # 禁用题库标识
self.COVER_RATE = self.cover_rate  # 覆盖率阈值
