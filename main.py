"""
Steps to download CSV:
 Chase website, lick "Accounts"
 Click the "more" dropdown menu
 Choose "spending summary ", top right(on laptop, left on mobile) 
 Theres a link that says "download transactions" CSV is an option in the download drop-downs
"""

import pandas as pd
import glob
import argparse
import os
import json
from collections import defaultdict

def load_exclusions(file_path):
    """
    Load vendor, keyword, and exact charge exclusions from a JSON file.
    """
    exclusions = {'vendors': set(), 'keywords': set(), 'charges': set()}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
            exclusions['vendors'] = set(map(str.lower, data.get('vendors', [])))
            exclusions['keywords'] = set(map(str.lower, data.get('keywords', [])))
            exclusions['charges'] = set(data.get('charges', []))
    return exclusions

def load_chase_statements(folder_path):
    """
    Load multiple CSV files from the specified folder and combine them into a single DataFrame.
    """
    folder_path = os.path.abspath(folder_path)  # Convert to absolute path if relative
    files = glob.glob(os.path.join(folder_path, "*.csv")) + glob.glob(os.path.join(folder_path, "*.CSV"))
    df_list = [pd.read_csv(file) for file in files]
    df = pd.concat(df_list, ignore_index=True).drop_duplicates()
    return df

def clean_data(df, exclusions):
    """
    Standardize column names, ensure correct data types, and apply exclusions.
    """
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    df = df.rename(columns={
        'transaction_date': 'date',
        'description': 'vendor',
        'amount': 'charge'
    })
    df['date'] = pd.to_datetime(df['date'])
    df['charge'] = df['charge'].astype(float)
    df = df.drop_duplicates(subset=['date', 'vendor', 'charge'])  # Remove exact duplicate transactions
    
    # Apply exclusions
    df = df[~df['vendor'].str.lower().isin(exclusions['vendors'])]
    df = df[~df['vendor'].str.lower().apply(lambda x: any(keyword in x for keyword in exclusions['keywords']))]
    df = df[~df['charge'].isin(exclusions['charges'])]
    
    return df[['date', 'vendor', 'charge']]

def find_recurring_charges(df):
    """
    Identify recurring charges based on vendors with the same charged amount appearing over multiple months.
    """
    recurring_charges = defaultdict(list)
    
    # Group by vendor and charge amount
    grouped = df.groupby(['vendor', 'charge'])
    for (vendor, charge), transactions in grouped:
        months = transactions['date'].dt.to_period('M').unique()
        if len(months) > 2:  # Consider it recurring if found in at least 3 different months
            recurring_charges[vendor].append({'amount': charge, 'months': list(months)})
    
    return recurring_charges

def top_vendors_by_spending(df, top_n=10):
    """
    Identify the top vendors by total money spent (negative charges only).
    """
    vendor_spending = df[df['charge'] < 0].groupby('vendor')['charge'].sum().reset_index()
    vendor_spending = vendor_spending.sort_values(by='charge', ascending=True)  # Sort by most negative
    return vendor_spending.head(top_n)

def most_expensive_charges(df, top_n=10):
    """
    Identify the most expensive individual transactions (negative charges only).
    """
    return df[df['charge'] < 0].nsmallest(top_n, 'charge')

def main(folder_path, exclusion_file):
    exclusions = load_exclusions(exclusion_file)
    df = load_chase_statements(folder_path)
    df = clean_data(df, exclusions)
    
    recurring_charges = find_recurring_charges(df)
    top_vendors = top_vendors_by_spending(df)
    expensive_charges = most_expensive_charges(df)
    
    print("Potential Recurring Charges:")
    for vendor, charges in recurring_charges.items():
        for charge in charges:
            print(f"Vendor: {vendor}, Amount: ${charge['amount']:.2f}, Recurs in Months: {', '.join(map(str, charge['months']))}")
    
    print("\nTop Vendors by Spending:")
    print(top_vendors)
    
    print("\nMost Expensive Charges:")
    print(expensive_charges)

if __name__ == "__main__":
    default_folder = os.path.join(os.getcwd(), "statements")
    parser = argparse.ArgumentParser(description="Analyze Chase credit card statements for recurring charges and top expenses.")
    parser.add_argument("folder_path", type=str, nargs='?', default=default_folder, help="Path to the folder containing Chase statement CSV files. Defaults to ./statements.")
    parser.add_argument("exclusion_file", type=str, nargs='?', default="exclusions.json", help="Path to the JSON file containing exclusions for vendors, keywords, and exact charges.")
    args = parser.parse_args()
    
    main(args.folder_path, args.exclusion_file)

