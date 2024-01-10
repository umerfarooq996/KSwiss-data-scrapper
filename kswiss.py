import os
import re
import json
import time
import random
import requests
import openpyxl
import traceback
import pandas as pd
from bs4 import BeautifulSoup

from config import email,password

from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

from script import (
    get_walmart_product_data,
    get_shopify_product_data,
    get_ebay_product_data,
    get_amazon_product_data,
)

VENDOR = "K-Swiss"

# CHROME_DIRECTORY = os.path.abspath("../ChromeUserDirectory")
CHROME_DIRECTORY = os.path.abspath("ChromeUserDirectory")
kids_gender = {"gender": "Male", "age_group": "Kids", "title_gender": "Kids"}
gender_dict = {
    "Mens": {
        "id": "7310",
        # "id": "6987",
        "gender": {"gender": "Male", "age_group": "Adult", "title_gender": "Men's"},
    },
    "Womens": {
        "id": "7311",
        # "id": "6991",
        "gender": {"gender": "Female", "age_group": "Adult", "title_gender": "Women's"},
    },
    "Grade School": {
        "id": "7384",
        # "id": "6995",
        "gender": {"gender": "Male", "age_group": "Big Kid", "title_gender": "Kids"},
    },
    "Pre School": {
        "id": "7388",
        # "id": "7000",
        "gender": {"gender": "Male", "age_group": "Little Kid", "title_gender": "Kids"},
    },
    "Toddlers": {
        "id": "7392",
        # "id": "7004",
        "gender": {"gender": "Male", "age_group": "Toddler", "title_gender": "Kids"},
    },
    "SMU SS 2024": {
    # "SMU FW 2023": {
        "id": "7399",
        # "id": "7015",
        "gender": {"gender": "Male", "age_group": "Mens", "title_gender": "Kids"},
    },
}

for key in gender_dict.keys():
    gender_dict[key].update(
        {"type": "shoes", "category": "Apparel & Accessories > Shoes", "weight": "1360"}
    )

products_data = []
export_switch = True

# TODO K-swiss related
k_swiss_lookup = {}


def sort_color_replacements(color_replacements):
    return sorted(color_replacements, key=len, reverse=True)


with open("look up.txt") as file:
    colors = file.read().split("\n")
    colors = sort_color_replacements(colors)
    for l in colors:
        l = l.strip(" ").split("=")
        k_swiss_lookup[l[0].strip()] = l[1].strip()


def lookup(text: str):
    while True:
        text = text.lower()
        replaced = (
            False  # Flag to check if any replacements were made in this iteration
        )
        for key, value in k_swiss_lookup.items():
            key = key.lower()
            if key in text:
                text = text.replace(key, value)
                replaced = True
                break
        if not replaced:
            break  # Exit the loop if no replacements were made in the iteration
    return text


def get_details(var):
    # data = []
    quantity = []
    debug_quantity = []
    available = True
    try:
        # TODO notify
        description = ""
        bullet_points = []
        try:
            description = BeautifulSoup(var["description"], "lxml").text
        except:
            pass
        try:
            bullet_points = (
                BeautifulSoup(var["description1"], "lxml").text.strip("\n").split("\n")
            )
        except:
            pass
        details_dict = {
            "cost": None,
            "price": None,
            "style_code": var["productNumber"],
            "title": var["productName"],
            "color": var["colorName"],
            "description": description,
            "features": [],
            "images": [],
            "sizes": [],
            "bullet_points": bullet_points,
            "stock": [],
        }
        (
            details_dict["style_code"],
            details_dict["title"],
            details_dict["color"],
            details_dict["description"],
        ) = (
            lookup(details_dict["style_code"]),
            lookup(details_dict["title"]),
            lookup(details_dict["color"]),
            lookup(details_dict["description"]),
        )

        image_keys = [
            "imageUrl",
            "image2Url",
            "image3Url",
            "image4Url",
            "image5Url",
            "image6Url",
        ]
        for img in image_keys:
            if img in var.keys():
                details_dict["images"].append(var[img])
        for size, val in var["groupSizeList"][0].items():
            idx = 0
            unit_price = val[idx]["unitPrice"]
            # msrp = val[idx]["msrp"]
            unit_price = round(unit_price)
            msrp = round(unit_price * 2)
            # print(unit_price,msrp)
            if not details_dict["cost"] and not details_dict["price"]:
                details_dict["cost"] = unit_price
                details_dict["price"] = msrp
            size = size.replace("H", ".5")
            available_date = val[idx]["availableDate"]
            if available_date != "AO":
                available = False
            dt = {
                "SKU": f'{details_dict["style_code"]}-{size}',
                "Upc": val[idx]["upc"],
                "Quantity": val[idx]["invStr"],
                "Cost": unit_price,
                "Price": msrp,
            }

            details_dict["stock"].append(
                {
                    "SKU": f"{details_dict['style_code']}-{size}",
                    "size": size,
                    "Upc": val[idx]["upc"],
                    "Quantity": val[idx]["invStr"],
                    "Cost": unit_price,
                    "Price": msrp,
                    "code": details_dict["style_code"],
                }
            )
            if available:
                quantity.append(dt)
                details_dict["sizes"].append(size)
            else:
                dt["Available Date"] = available_date
                debug_quantity.append(dt)
                # debug_quantity.append(dt)
    except:
        print(var["productNumber"])
        #        with open("temp.json", "w") as file:
        #            json.dump(var, file)
        traceback.print_exc()
    if not available:
        details_dict = None

    return details_dict, quantity, debug_quantity


def getDescription(a1, a2, a3, a4):
    a2 = [f"<li>{x}</li>" for x in a2]
    a2 = "".join(a2)
    a2 = f"<ul>{a2}</ul>".replace("’", "'")
    a4 = [f"<li>{x}</li>" for x in a4]
    a4 = "".join(a4)
    a4 = f"<div><span>Features:</span> <ul>{a4}</ul></div>".replace("’", "'")
    a1 = f"<div>{a1}</div>"
    a3 = f"<div><span>Style #:</span><span>{a3}</span></div>"
    desc = f"{a1}{a2}{a4}{a3}"
    return desc


def getCost(p):
    if p:
        p = p.replace("$", "").strip()
        p = round(float(p))
        p = int(p)
        return p


def try_again(ls, ind):
    try:
        return ls[ind]
    except:
        return None


def remove_double_spaces(text):
    return re.sub(r" +", " ", text)


def is_available(quantity, key):
    for q in quantity:
        if q["key"] == key:
            date_obj = datetime.fromisoformat(q["release_date"])
            # Get the current date and time
            current_date = datetime.now()
            current_date = current_date.replace(tzinfo=date_obj.tzinfo)
            # Compare the dates
            if date_obj <= current_date:
                return True, q["quantity"]
    return False, -1


def get_quantity(js):
    keys_to_extract = ["key", "available_on", "quantity", "release_date"]
    q_data = [
        {key: item[key] for key in keys_to_extract} for item in js["stock_shipments"]
    ]
    return q_data


def get_parsed_quantity(js, quantity_upc):
    debug_data = []
    keys_to_extract = ["key", "available_on", "quantity", "release_date"]
    for row in js["stock_shipments"]:
        try:
            dt = {key: row[key] for key in keys_to_extract}
            ls = dt["key"].split(" ")
            style_code, size = ls[0], ls[-1]
            size = get_size(size)
            dt["key"] = f"{style_code}-{size}"
            debug_data.append(dt)
            found = False
            for q in quantity_upc:
                if q["SKU"] == dt["key"]:
                    found = True
                    q["Quantity"] = dt["quantity"]
                    break
            # if not found:
            #     print(dt["key"])
        except:
            traceback.print_exc()
            # input(row)
    return quantity_upc, debug_data


quantity = []
debug_quantity = []


def scrapper(data, dt):
    for prd in data["detail"]:
        var, qu, d_qu = get_details(prd)
        quantity.extend(qu)
        debug_quantity.extend(d_qu)
        if var:
            var.update(dt)
            # Adjust not found values
            try:
                var["url"] = None
                var["widths"] = []
                # get_data(var)
                products_data.append(var)
            except:
                traceback.print_exc()
                input(var)
    # get_amazon_product_data(products_data)
    # get_amazon_quantity_data(products_data)


def main():
    cookies = get_browser_session_token()
    # session_token=None
    for key, value in gender_dict.items():
        print("Fetching -> ", key)
        # with open(f"backup/{key}.json", "r") as file:
        # 	data = json.load(file)
        data = get_json(value["id"],cookies)
        # os.makedirs("data_backup",exist_ok=True)
        # file = key + ".json"
        # file = os.path.join("data_backup", key) + ".json"
        # with open(file, "w") as file:
            # json.dump(data, file)
        scrapper(data, value)
        # break

    file_path = "Template.xlsx"  # Replace with the path to your existing Excel file
    workbook = openpyxl.load_workbook(file_path)
    vendor = "K-Swiss"
    get_shopify_product_data(products_data, vendor, workbook)
    get_ebay_product_data(products_data, vendor, workbook)
    get_walmart_product_data(products_data, vendor, workbook)
    get_amazon_product_data(products_data, vendor, workbook)

    current_date = datetime.now().strftime("%Y-%m-%d")
    workbook.save(f"{vendor}_{current_date}.xlsx")
    workbook.close()
    pd.DataFrame(debug_quantity).to_csv(
        f"Debug_{vendor}_{current_date}.xlsx", index=False
    )


def add_upc_barcode(quantity):
    for d_r, q_r in zip(products_data, quantity):
        if d_r["Variant SKU"] != q_r["SKU"]:
            print("Not found in upc barcode -> ", d_r["Variant SKU"])
        else:
            d_r["Variant Barcode"] = q_r["Upc"]
            d_r["Google Shopping / MPN"] = q_r["Upc"]


def get_size(size):
    try:
        size = int(size)
        if (
            len(str(size)) > 1
            and size != 10
            and size != 11
            and size != 12
            and size != 13
            and size != 14
            and size != 15
            and size != 16
        ):
            size = int(size) / 10
        return size
    except (ValueError, TypeError):
        raise ValueError(f"Invalid size: {size}")


def get_json(id,cookies):
    headers = {
        "authority": "kswiss-us.hubsoft.com",
        "accept": "application/json, text/plain, */*",
        "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
        # 'cookie': 'JSESSIONID=C9F5A922620255D47C606B60FDAA22D1; HsSessKey136=C9F5A922620255D47C606B60FDAA22D1; firstName=Mark; name=mbertignoli; locale=en_US; AWSALB=fHcbFeCKNuKrzsGLR+445ySFXJ75g5H7sINWv5POWeN/jc0vDkZZ0PFF7ErzB2hCbJzdCg/NX03QEAf2+8BlKMOS1MqxviAGw9Qq0wC9tUfuAsZX3s+XyQwQwmDI',
        "referer": "https://kswiss-us.hubsoft.com/availability/menus/7310/list?from=0&to=2",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    }

    params = {
        "viewType": "L",
        "preSeason": "0",
        "pageSize": "1000",
        "startIndex": "0",
        "includeAllSeason": "1",
        "markFavorites": "1",
        "showOnlyImmedAvail": "0",
        "showOnlyAvail": "0",
        "showIfAvailAllSize": "0",
        "sortProdBy": "seasonOrder",
        "subMenuId": id,
        "warehouseId": "281",
        "sessionToken": cookies["HsSessKey136"],
    }
    response = requests.get(
        "https://kswiss-us.hubsoft.com/cxf/order2/getDraftOrderItems",
        params=params,
          cookies=cookies,
        headers=headers,
    )
    return response.json()


def get_browser_session_token():
    chrome_profile_directory = CHROME_DIRECTORY
    chrome_options = Options()
    # Use the specified profile directory
    chrome_options.add_argument(f"--user-data-dir={chrome_profile_directory}")
    # Maximize the browser window on start
    chrome_options.add_argument("--start-maximized")
    # Create a Chrome WebDriver instance
    driver = webdriver.Chrome(options=chrome_options)
    # Open a website
    url = "https://kswiss-us.hubsoft.com/login?upd=1694805590892"
    url = "https://kswiss-us.hubsoft.com/"
    driver.get(url)

    time.sleep(random.uniform(2, 3))
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CLASS_NAME, "username"))
        )
    except:
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "userNameId"))
            ).send_keys(email)
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "userPasswordId"))
            ).send_keys(password)
            WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CLASS_NAME, "indigo"))
            ).click()
        except:
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.ID, "userPasswordId"))
            ).send_keys(password)
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.CLASS_NAME, "indigo"))
            ).click()
    time.sleep(4)
    cookies={}
    for row in driver.get_cookies():
        cookies[row["name"]]=row["value"]
    
    return cookies


if __name__ == "__main__":
    try:
        main()
    except:
        traceback.print_exc()
    input("Finished")
