import os
import asyncio
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains

chrome_options = Options()
# chrome_options.add_argument("--headless")
driver = webdriver.Chrome(options=chrome_options)

url = "https://fr.coinalyze.net/bitcoin/funding-rate/"
driver.get(url)
widget_xpath = '/html/body/div/div[2]/div/div[4]/div[2]/div'
time.sleep(8)
widget = driver.find_element(by=By.XPATH, value=widget_xpath)
driver.execute_script("arguments[0].scrollIntoView();", widget)
driver.implicitly_wait(5)
widget.screenshot("widget.png")

driver.quit()