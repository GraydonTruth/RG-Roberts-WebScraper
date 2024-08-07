import asyncio
import aiohttp
from bs4 import BeautifulSoup
import csv
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import random
import json
import os
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# List of User-Agents to rotate
DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]

# Helper Functions
def get_user_agents():
    return [line.strip() for line in user_agents_text.get("1.0", tk.END).strip().split('\n')]

def get_proxies():
    return proxy_var.get()

def get_custom_headers():
    try:
        return json.loads(custom_headers_var.get())
    except json.JSONDecodeError:
        return {}

def display_error(message):
    messagebox.showerror("Error", message)

# Scraping Functions
async def fetch_page(session, url, retry_count=3):
    headers = {"User-Agent": random.choice(get_user_agents() or DEFAULT_USER_AGENTS)}
    headers.update(get_custom_headers())
    
    try:
        async with session.get(url, headers=headers, proxy=get_proxies()) as response:
            response.raise_for_status()
            logging.debug(f"Fetched page content from {url}")
            return await response.text()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        if retry_count > 0:
            logging.warning(f"Retrying {url} ({3 - retry_count + 1}/3)...")
            return await fetch_page(session, url, retry_count - 1)
        error_msg = f"Error fetching {url}: {e}"
        logging.error(error_msg)
        display_error(error_msg)
    return None

async def scrape_quotes(session, url, quote_tag, quote_class, author_tag, author_class):
    page_content = await fetch_page(session, url)
    if page_content is None:
        return []

    soup = BeautifulSoup(page_content, "html.parser")
    logging.debug("Scraping quotes and authors")
    quotes = soup.find_all(quote_tag, class_=quote_class)
    authors = soup.find_all(author_tag, class_=author_class)
    
    if not quotes or not authors:
        logging.warning("No quotes or authors found on the page.")
    
    return [(quote.text.strip().replace('"', '""'), author.text.strip().replace('"', '""')) for quote, author in zip(quotes, authors)]

async def scrape_all_quotes(base_url, quote_tag, quote_class, author_tag, author_class, total_pages, delay, progress_callback):
    all_quotes = []
    page_number = 1

    base_url = base_url.rstrip('/') + '/'

    async with aiohttp.ClientSession() as session:
        while page_number <= total_pages:
            url = f"{base_url}page/{page_number}/"
            logging.info(f"Fetching {url}")
            quotes = await scrape_quotes(session, url, quote_tag, quote_class, author_tag, author_class)
            
            if not quotes:
                logging.info(f"No quotes found on page {page_number}. Ending scrape.")
                break
            
            all_quotes.extend([(page_number, *quote) for quote in quotes])
            page_number += 1

            progress_callback(page_number, total_pages, len(all_quotes))
            await asyncio.sleep(delay)

    return all_quotes

def save_to_csv(quotes, filename, base_url):
    try:
        with open(filename, "w", newline='', encoding='utf-8') as file:
            writer = csv.writer(file, quoting=csv.QUOTE_ALL)
            writer.writerow(["Scrape Date", "Base URL", "PAGE", "QUOTE", "AUTHOR"])
            scrape_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            writer.writerows([scrape_date, base_url] + list(row) for row in quotes)
        logging.info(f"Data saved to {filename}")
    except IOError as e:
        logging.error(f"Error writing to file {filename}: {e}")

async def scrape_and_save(base_url, output_filename, quote_tag, quote_class, author_tag, author_class, total_pages, delay, progress_callback):
    quotes = await scrape_all_quotes(base_url, quote_tag, quote_class, author_tag, author_class, total_pages, delay, progress_callback)
    
    if quotes:
        save_to_csv(quotes, output_filename, base_url)
        return "Scraping completed!"
    return "No quotes found or an error occurred."

# GUI Functions
def browse_file():
    filename = filedialog.asksaveasfilename(defaultextension=".csv",
                                           filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    if filename:
        file_path_var.set(filename)

def start_scraping():
    base_url = url_entry.get()
    output_filename = file_path_var.get()
    quote_tag = quote_tag_entry.get()
    quote_class = quote_class_entry.get()
    author_tag = author_tag_entry.get()
    author_class = author_class_entry.get()
    total_pages = int(total_pages_entry.get())
    delay = float(delay_entry.get())

    if not base_url or not output_filename:
        messagebox.showerror("Input Error", "Please provide both URL and output file name.")
        return

    status_var.set("Scraping in progress...")
    root.update_idletasks()
    
    start_button.config(state=tk.DISABLED)
    clear_button.config(state=tk.DISABLED)

    def progress_callback(page_number, total_pages, collected_quotes):
        progress_var.set(f"Scraping page {page_number} of {total_pages}...")
        progress_detail_var.set(f"Collected {collected_quotes} quotes so far")
        progress_bar['value'] = (page_number / total_pages) * 100
        root.update_idletasks()

    async def run_scraping():
        result = await scrape_and_save(base_url, output_filename, quote_tag, quote_class, author_tag, author_class, total_pages, delay, progress_callback)
        status_var.set(result)
        messagebox.showinfo("Result", result)
        start_button.config(state=tk.NORMAL)
        clear_button.config(state=tk.NORMAL)

    asyncio.run(run_scraping())

def clear_inputs():
    url_entry.delete(0, tk.END)
    file_path_var.set("")
    quote_tag_entry.delete(0, tk.END)
    quote_tag_entry.insert(0, "span")
    quote_class_entry.delete(0, tk.END)
    quote_class_entry.insert(0, "text")
    author_tag_entry.delete(0, tk.END)
    author_tag_entry.insert(0, "small")
    author_class_entry.delete(0, tk.END)
    author_class_entry.insert(0, "author")
    total_pages_entry.delete(0, tk.END)
    total_pages_entry.insert(0, "11")
    delay_entry.delete(0, tk.END)
    delay_entry.insert(0, "2.0")
    user_agents_text.delete("1.0", tk.END)
    user_agents_text.insert(tk.END, "\n".join(DEFAULT_USER_AGENTS))
    proxy_var.set("")
    custom_headers_var.set("")

def save_config():
    config = {
        "url": url_entry.get(),
        "file_path": file_path_var.get(),
        "quote_tag": quote_tag_entry.get(),
        "quote_class": quote_class_entry.get(),
        "author_tag": author_tag_entry.get(),
        "author_class": author_class_entry.get(),
        "total_pages": total_pages_entry.get(),
        "delay": delay_entry.get(),
        "user_agents": user_agents_text.get("1.0", tk.END).strip().split('\n'),
        "proxy": proxy_var.get(),
        "custom_headers": custom_headers_var.get()
    }

    config_path = filedialog.asksaveasfilename(defaultextension=".json",
                                               filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
    if config_path:
        try:
            with open(config_path, 'w') as config_file:
                json.dump(config, config_file, indent=4)
            messagebox.showinfo("Success", f"Configuration saved to {config_path}")
        except IOError as e:
            messagebox.showerror("Error", f"Error saving configuration: {e}")

def show_help():
    help_message = (
        "R.G Roberts Scraper\n\n"
        "This scraper is designed to extract quotes and authors from the website "
        "https://quotes.toscrape.com/. To use the scraper:\n\n"
        "1. Enter the base URL of the site you want to scrape.\n"
        "2. Specify the output CSV file where the scraped data will be saved.\n"
        "3. Fill in the HTML tags and classes for quotes and authors as needed.\n"
        "4. Set the number of pages you want to scrape and the delay between requests.\n"
        "5. Click 'Start Scraping' to begin.\n\n"
        "Make sure to follow the website's terms of service and use scraping responsibly."
    )
    messagebox.showinfo("Help", help_message)

# GUI Setup
root = tk.Tk()
root.title("R.G Roberts Scraper")

# URL
tk.Label(root, text="Base URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
url_entry = tk.Entry(root, width=50)
url_entry.grid(row=0, column=1, padx=5, pady=5)

# Output File
tk.Label(root, text="Output File:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
file_path_var = tk.StringVar()
tk.Entry(root, textvariable=file_path_var, width=50).grid(row=1, column=1, padx=5, pady=5)
tk.Button(root, text="Browse", command=browse_file).grid(row=1, column=2, padx=5, pady=5)

# Quote Tag
tk.Label(root, text="Quote Tag:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
quote_tag_entry = tk.Entry(root)
quote_tag_entry.grid(row=2, column=1, padx=5, pady=5)
quote_tag_entry.insert(0, "span")

# Quote Class
tk.Label(root, text="Quote Class:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
quote_class_entry = tk.Entry(root)
quote_class_entry.grid(row=3, column=1, padx=5, pady=5)
quote_class_entry.insert(0, "text")

# Author Tag
tk.Label(root, text="Author Tag:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
author_tag_entry = tk.Entry(root)
author_tag_entry.grid(row=4, column=1, padx=5, pady=5)
author_tag_entry.insert(0, "small")

# Author Class
tk.Label(root, text="Author Class:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
author_class_entry = tk.Entry(root)
author_class_entry.grid(row=5, column=1, padx=5, pady=5)
author_class_entry.insert(0, "author")

# Total Pages
tk.Label(root, text="Total Pages:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
total_pages_entry = tk.Entry(root)
total_pages_entry.grid(row=6, column=1, padx=5, pady=5)
total_pages_entry.insert(0, "11")

# Delay
tk.Label(root, text="Delay (seconds):").grid(row=7, column=0, sticky=tk.W, padx=5, pady=5)
delay_entry = tk.Entry(root)
delay_entry.grid(row=7, column=1, padx=5, pady=5)
delay_entry.insert(0, "2.0")

# User Agents
tk.Label(root, text="User Agents (one per line):").grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
user_agents_text = tk.Text(root, height=4, width=50)
user_agents_text.grid(row=8, column=1, padx=5, pady=5)
user_agents_text.insert(tk.END, "\n".join(DEFAULT_USER_AGENTS))

# Proxy
tk.Label(root, text="Proxy (optional):").grid(row=9, column=0, sticky=tk.W, padx=5, pady=5)
proxy_var = tk.StringVar()
tk.Entry(root, textvariable=proxy_var, width=50).grid(row=9, column=1, padx=5, pady=5)

# Custom Headers
tk.Label(root, text="Custom Headers (JSON format):").grid(row=10, column=0, sticky=tk.W, padx=5, pady=5)
custom_headers_var = tk.StringVar()
tk.Entry(root, textvariable=custom_headers_var, width=50).grid(row=10, column=1, padx=5, pady=5)

# Status
status_var = tk.StringVar()
status_var.set("Ready")
tk.Label(root, textvariable=status_var).grid(row=11, column=0, columnspan=4, padx=5, pady=5)

# Progress
progress_var = tk.StringVar()
progress_var.set("")
tk.Label(root, textvariable=progress_var).grid(row=12, column=0, columnspan=4, padx=5, pady=5)

progress_detail_var = tk.StringVar()
progress_detail_var.set("")
tk.Label(root, textvariable=progress_detail_var).grid(row=13, column=0, columnspan=4, padx=5, pady=5)

progress_bar = ttk.Progressbar(root, orient=tk.HORIZONTAL, length=400, mode='determinate')
progress_bar.grid(row=14, column=0, columnspan=4, padx=5, pady=5)

# Buttons
start_button = tk.Button(root, text="Start Scraping", command=start_scraping)
start_button.grid(row=15, column=0, padx=5, pady=5)

clear_button = tk.Button(root, text="Clear", command=clear_inputs)
clear_button.grid(row=15, column=1, padx=5, pady=5)

save_config_button = tk.Button(root, text="Save Config", command=save_config)
save_config_button.grid(row=15, column=2, padx=5, pady=5)

help_button = tk.Button(root, text="Help", command=show_help)
help_button.grid(row=15, column=3, padx=5, pady=5)

root.mainloop()
