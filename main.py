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
from collections import defaultdict

def load_chase_statements(folder_path):
    """
    Load multiple CSV files from the specified folder and combine them into a single DataFrame.
    """
    folder_path = os.path.abspath(folder_path)  # Convert to absolute path if relative
    files = glob.glob(os.path.join(folder_path, "*.csv")) + glob.glob(os.path.join(folder_path, "*.CSV"))
    df_list = [pd.read_csv(file) for file in files]
    df = pd.concat(df_list, ignore_index=True)
    return df

def clean_data(df):
    """
    Standardize column names and ensure correct data types.
    """
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    df = df.rename(columns={
        'transaction_date': 'date',
        'description': 'vendor',
        'amount': 'charge'
    })
    df['date'] = pd.to_datetime(df['date'])
    df['charge'] = df['charge'].astype(float)
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

def main(folder_path):
    df = load_chase_statements(folder_path)
    df = clean_data(df)
    recurring_charges = find_recurring_charges(df)
    
    print("Potential Recurring Charges:")
    for vendor, charges in recurring_charges.items():
        for charge in charges:
            print(f"Vendor: {vendor}, Amount: ${charge['amount']:.2f}, Recurs in Months: {', '.join(map(str, charge['months']))}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Chase credit card statements for recurring charges.")
    parser.add_argument("folder_path", type=str, nargs='?', default=os.getcwd()+"/statements", help="Path to the folder containing Chase statement CSV files. Defaults to current directory.")
    args = parser.parse_args()
    
    main(args.folder_path)