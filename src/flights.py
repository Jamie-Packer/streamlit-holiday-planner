""" momondo for scraping flight prices  """

# libraries
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import undetected_chromedriver as uc
import time


def fetch_flightprice(dest_out, dest_in, date):
    """Fetch flight prices (best) with input of dest_out (where the flyer is flying from), 
    dest_in (where the flyer is flying to), and date (date of flight). This function web scrapes
    from momondo using selenium. When calling, input strings in this format:

    fetch_flightprice(
    "Manchester",
    "Barcelona",
    "20/07/2026")
    
    Returns a dictionary of the best "price" and "duration" for a flight with the given inputs
    """
    # create driver using my version of chrome (148)
    driver = uc.Chrome(version_main=148)
    # load momondo
    driver.maximize_window()   # change window size
    driver.get("https://www.momondo.co.uk")
    # wait 2 seconds
    time.sleep(2)
    # create wait variable
    wait = WebDriverWait(driver, 10)

    ## STAGE 1 - click accept cookies
    cookie_button = wait.until(
    EC.element_to_be_clickable(   # wait for the object to be clickable
        (By.XPATH, "//button[contains(., 'Accept')]"))   # for this Xpath - accept cookies
    )
    cookie_button.click()   # click button

    ## STAGE 2 - click ai button
    open_ai = driver.find_element(
    By.XPATH,
    "//*[@aria-label='Open AI chat']")
    open_ai.click()    # open the ai chatbot
    
    ## STAGE 3 - type the flight information in
    chat_box = wait.until(
    EC.presence_of_element_located(
        (By.ID, "dialog-ai-chat-text-input")))
    chat_box.send_keys(
        f"Direct flights from {dest_out} to {dest_in} on {date}")   # parameters input
    chat_box.send_keys(Keys.ENTER)   # press enter

    ## STAGE 4 - Wait 8 seconds - temporary fix for now
    # Temporary solution while testing
    time.sleep(5)

    ## STAGE 5 - close ai sidebar - required to access 'best' element
    close_ai = wait.until(
    EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "[aria-label='Close AI chat']")))   # locate element
    close_ai.click()   # click close

    ## STAGE 6 - extract information from 'best' card
    best_card = wait.until(
    EC.presence_of_element_located(
        (By.CSS_SELECTOR, "[data-content='bestflight_a']")))

    ## STAGE 7 - return information
    lines = best_card.text.split("\n")
    price, duration = lines[1].split(" • ")

    result = {
        "price": price,
        "duration": duration
    }

    driver.quit()   # quit browser
    return result   # return dictionary
