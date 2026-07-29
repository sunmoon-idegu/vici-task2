# vici-task2

This document contains the original task statement and defines the overall requirements for extracting Item-level content from SEC Form 10-K filings.

## 題目二：SEC 10-K 財報 Item-level 結構化抽取

美國上市公司每年向 SEC 提交的 10-K 年度報告有規範的結構（Part I–IV 底下的 Item 1–16），但實際檔案格式變異極大。

請做一個 pipeline：從原始的 10-K filing 抽取出各個 item，讓它們能被獨立取用。請自建 evaluation set 驗證系統的可靠性，並提供網站前端，讓我們可以提交或選擇 filings、檢視抽取出的 items，並理解抽取信心或失敗案例。我們會用自己挑的 filings 驗證。

請在 README 或前端中清楚列出：

- 你認為目前抽取得好的 filings 或公司，並提供例子
- 目前仍有困難、不穩定，或尚未支援的 filings 或公司，並提供具體失敗案例

**我們會看**：在格式變異下如何保持穩健、在沒有公開 ground truth 的情況下如何驗證自己、edge case 的處理、成本紀律，以及你對效能、擴充性與正確性驗證的分析。
