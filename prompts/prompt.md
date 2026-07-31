"""
Author: Yuming Lu

This prompt file does not cover the entire prompt history.
It covers the core idea and order of how I build this project.
"""

1. Please read the README.md file. Let's start with a simple python function that solves this problem. Ignore the frontend and backend setting now. Just focus on the functionality.

2. I want the extraction method to be three layered. If the result of the first layer failed, then move on to the next layer, and so on.
My thought of the layer is: First, use regular expression. Second, use language model to extract but a cheap model. Third, use langauge model to extract but a stronger one. Use Anthropic.

3. Let's discuss the meaning of "the result of the first layer failed". We need some evaluation method to calculate the confidence score.

4. Please find the test case and evaluate the confidence score of these test cases.

5. Let's build the backend using Python fastAPI. I want the folder be well-structured. router -> controller -> services. Also, evaluation and repositories.

6. Build a React SPA frontend with Vite and make sure the api connection with backend is working.