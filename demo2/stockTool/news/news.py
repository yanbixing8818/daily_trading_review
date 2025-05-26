import akshare as ak
import streamlit as st
import jieba
import pandas as pd
from collections import Counter
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from datetime import datetime, timedelta
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import re


# 解决中文乱码问题
plt.rcParams['font.sans-serif'] = ['STHeiti']  # 苹果系统字体
#plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['axes.unicode_minus'] = False
is_mac = True

# 初始化智谱 AI
zhipu_api_key = "XXXX"
llm = ChatOpenAI(
    temperature=0.95,
    model="glm-4-flash",
    openai_api_key=zhipu_api_key,
    openai_api_base="https://open.bigmodel.cn/api/paas/v4/"
)

# 停用词列表
stop_words = set([
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要',
    '去', '你',
    '会', '着', '没有', '看', '好', '自己', '这', '么', '个', '什么', '那', '他', '吗', '把', '给', '让', '但', '还',
    '可以', '这个',
    '啊', '呢', '吧', '啦', '嗯', '哦', '哈', '呀', '哎', '唉', '嘿', '嗨', '哇', '呵', '嘛', '喂', '诶', '哼', '咦',
    '呜', '哟',
    '，', '。', '、', '：', '；', '！', '？', '"', '"', ''', ''', '（', '）', '【', '】', '《', '》', '…', '—', '－', '～',
    '·', '「', '」', '『', '』', '〈', '〉', '﹏', '′', '°', '℃', '＄', '￥', '％', '＠', '＆', '＃', '＊', '‰', '※', '±', '∶',
    '∵', '∴', '∷', '∽', '≈', '≌', '≠', '≤', '≥', '∞', '∝', '∫', '∮', '∑', '∏', '∈', '∋', '∩', '∪', '∨', '∧', '∀', '∃',
    '∇', '∅', '∆', '∇', '∉', '∋', '∏', '∑', '∗', '∝', '∞', '∠', '∡', '∢', '∣', '∤', '∥', '∦', '∧', '∨', '∩', '∪', '∫',
    '∬', '∭', '∮', '∯', '∰', '∱', '∲', '∳', '∴', '∵', '∶', '∷', '∸', '∹', '∺', '∻', '∼', '∽', '∾', '∿', '≀', '≁', '≂',
    '≃', '≄', '≅', '≆', '≇', '≈', '≉', '≊', '≋', '≌', '≍', '≎', '≏', '≐', '≑', '≒', '≓', '≔', '≕', '≖', '≗', '≘', '≙',
    '≚', '≛', '≜', '≝', '≞', '≟', '≠', '≡', '≢', '≣', '≤', '≥', '≦', '≧', '≨', '≩', '≪', '≫', '≬', '≭', '≮', '≯', '≰',
    '≱', '≲', '≳', '≴', '≵', '≶', '≷', '≸', '≹', '≺', '≻', '≼', '≽', '≾', '≿', '⊀', '⊁', '⊂', '⊃', '⊄', '⊅', '⊆', '⊇',
    '⊈', '⊉', '⊊', '⊋', '⊌', '⊍', '⊎', '⊏', '⊐', '⊑', '⊒', '⊓', '⊔', '⊕', '⊖', '⊗', '⊘', '⊙', '⊚', '⊛', '⊜', '⊝', '⊞',
    '⊟', '⊠', '⊡', '⊢', '⊣', '⊤', '⊥', '⊦', '⊧', '⊨', '⊩', '⊪', '⊫', '⊬', '⊭', '⊮', '⊯', '⊰', '⊱', '⊲', '⊳', '⊴', '⊵',
    '⊶', '⊷', '⊸', '⊹', '⊺', '⊻', '⊼', '⊽', '⊾', '⊿', '⋀', '⋁', '⋂', '⋃', '⋄', '⋅', '⋆', '⋇', '⋈', '⋉', '⋊', '⋋', '⋌',
    '⋍', '⋎', '⋏', '⋐', '⋑', '⋒', '⋓', '⋔', '⋕', '⋖', '⋗', '⋘', '⋙', '⋚', '⋛', '⋜', '⋝', '⋞', '⋟', '⋠', '⋡', '⋢', '⋣',
    '⋤', '⋥', '⋦', '⋧', '⋨', '⋩', '⋪', '⋫', '⋬', '⋭', '⋮', '⋯', '⋰', '⋱', '⋲', '⋳', '⋴', '⋵', '⋶', '⋷', '⋸', '⋹', '⋺',
    '⋻', '⋼', '⋽', '⋾', '⋿'
])


# 获取新闻数据
@st.cache_data
def get_news_data(date):
    news_data = ak.news_cctv(date)
    print(news_data)
    return news_data


# 分词和统计
def process_news(news_data):
    all_words = []
    for content in news_data['content']:
        # 使用正则表达式去除标点符号
        content = re.sub(r'[^\w\s]', '', content)
        words = jieba.cut(content)
        # 过滤停用词
        words = [word for word in words if word not in stop_words and len(word) > 1]
        all_words.extend(words)

    word_count = Counter(all_words)
    return word_count


# 生成词云图
def generate_wordcloud(word_count):
    if is_mac:
        wc = WordCloud(font_path="/System/Library/fonts/PingFang.ttc", width=800, height=400, background_color='white')
    else:
        wc = WordCloud(width=800, height=400, background_color='white')

    wc.generate_from_frequencies(word_count)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation='bilinear')
    ax.axis('off')
    return fig




# 使用 LangChain 和智谱 GLM-4-flash 生成投资建议
def generate_investment_advice(news_content):
    prompt = PromptTemplate(
        input_variables=["news"],
        template="基于以下新闻内容，给出3-5条具体的股票投资建议：\n{news}\n\n投资建议："
    )

    chain = LLMChain(llm=llm, prompt=prompt)

    response = chain.run(news=news_content)

    # 将建议拆分成列表
    advice_list = response.strip().split("\n")
    return advice_list


# Streamlit应用
def main():
    st.title("新闻联播股票热点分析")

    # 日期选择
    yesterday = datetime.now() - timedelta(days=1)
    selected_date = st.date_input("选择新闻日期", value=yesterday)
    date_str = selected_date.strftime("%Y%m%d")

    news_data = get_news_data(date_str)
    word_count = process_news(news_data)


    st.subheader("热点词云")
    wordcloud_fig = generate_wordcloud(word_count)
    st.pyplot(wordcloud_fig)


    st.subheader("投资建议")
    news_content = "\n".join(news_data['content'].tolist())
    advice = generate_investment_advice(news_content)
    for item in advice:
        st.write(item)

    st.subheader("热点词汇Top 10")
    top_words = pd.DataFrame(word_count.most_common(10), columns=['词汇', '频次'])
    st.table(top_words)


if __name__ == "__main__":
    main()