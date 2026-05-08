const api = require('../../utils/api')

Page({
  data: {
    resumeText: '',
    matches: [],
    loading: false,
    hasMatch: false,
    city: '上海'
  },

  onResumeInput(e) {
    this.setData({ resumeText: e.detail.value })
  },

  async doMatch() {
    if (!this.data.resumeText.trim()) {
      wx.showToast({ title: '请粘贴简历文本', icon: 'none' })
      return
    }
    this.setData({ loading: true })
    try {
      const result = await api.matchResume(this.data.resumeText, this.data.city, 30)
      this.setData({
        matches: result.top_matches || [],
        loading: false,
        hasMatch: true
      })
    } catch (e) {
      this.setData({ loading: false })
      wx.showToast({ title: '匹配失败', icon: 'none' })
    }
  },

  goDetail(e) {
    wx.navigateTo({ url: `/pages/detail/detail?id=${e.currentTarget.dataset.id}` })
  },

  // Quick fill sample resume
  fillSample() {
    const sample = `教育背景
某大学 数据科学与大数据技术 本科 2024-2027
主修课程：Python、SQL、概率论、统计学、机器学习

技能
Python、SQL、Excel、Tableau、Power BI、统计学分析

实习经历
某互联网公司 数据分析实习生
- 搭建用户行为分析看板，覆盖日活/留存/转化等核心指标
- 用SQL+Python进行AB测试效果分析，推动策略优化
- 撰写数据分析报告，辅助业务决策

项目经历
校园招聘数据分析
- 爬取5000+岗位数据，清洗分析
- 构建岗位-简历匹配模型，匹配准确率85%+`
    this.setData({ resumeText: sample })
  }
})
