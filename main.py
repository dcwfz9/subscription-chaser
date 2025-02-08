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
    exclusions = {
        'recurring': {'vendors': set(), 'keywords': set(), 'charges': set()},
        'spending': {'vendors': set(), 'keywords': set(), 'charges': set()}
    }
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                data = json.load(f)
                for category in ['recurring', 'spending']:
                    exclusions[category]['vendors'] = set(map(str.lower, data.get(category, {}).get('vendors', []) or []))
                    exclusions[category]['keywords'] = set(map(str.lower, data.get(category, {}).get('keywords', []) or []))
                    exclusions[category]['charges'] = set(data.get(category, {}).get('charges', []) or [])
            except json.JSONDecodeError:
                print("Warning: Exclusion file is not valid JSON. Ignoring exclusions.")
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

def clean_data(df, exclusions, category):
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
    df = df[~df['vendor'].str.lower().isin(exclusions[category]['vendors'])]
    df = df[~df['vendor'].str.lower().apply(lambda x: any(keyword in x for keyword in exclusions[category]['keywords']))]
    df = df[~df['charge'].isin(exclusions[category]['charges'])]
    
    return df[['date', 'vendor', 'charge']]

def find_recurring_charges(df):
    """
    Identify recurring charges based on vendors with the same charged amount appearing over multiple months.
    Sort them by total amount spent.
    """
    recurring_charges = defaultdict(lambda: defaultdict(lambda: {'total_spent': 0, 'months': set()}))
    
    # Group by vendor and charge amount
    grouped = df.groupby(['vendor', 'charge'])
    for (vendor, charge), transactions in grouped:
        months = set(transactions['date'].dt.to_period('M'))
        if len(months) > 2:  # Consider it recurring if found in at least 3 different months
            total_spent = charge * len(transactions)
            recurring_charges[vendor][charge]['total_spent'] = total_spent
            recurring_charges[vendor][charge]['months'] = months
    
    # Flatten and sort by most negative total spent
    sorted_recurring = sorted(
        [(vendor, charge, data['total_spent'], data['months'])
         for vendor, charges in recurring_charges.items() for charge, data in charges.items()],
        key=lambda x: x[2]
    )
    return sorted_recurring

def top_vendors_by_spending(df, top_n=25):
    """
    Identify the top vendors by total money spent (negative charges only).
    """
    vendor_spending = df[df['charge'] < 0].groupby('vendor')['charge'].sum().reset_index()
    vendor_spending = vendor_spending.sort_values(by='charge', ascending=True)  # Sort by most negative
    return vendor_spending.head(top_n)

def most_expensive_charges(df, top_n=25):
    """
    Identify the most expensive individual transactions (negative charges only).
    """
    return df[df['charge'] < 0].nsmallest(top_n, 'charge')

def main(folder_path, exclusion_file):
    exclusions = load_exclusions(exclusion_file)
    df = load_chase_statements(folder_path)
    
    df_recurring = clean_data(df, exclusions, 'recurring')
    recurring_charges = find_recurring_charges(df_recurring)
    
    df_spending = clean_data(df, exclusions, 'spending')
    top_vendors = top_vendors_by_spending(df_spending)
    expensive_charges = most_expensive_charges(df_spending)
    
    print("Potential Recurring Charges:")
    for vendor, charge, total_spent, months in recurring_charges:
        print(f"Vendor: {vendor}, Total Spent: ${total_spent:.2f}, Amount: ${charge:.2f}, Recurs in Months: {', '.join(map(str, months))}")
    
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
