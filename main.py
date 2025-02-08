import pandas as pd
import glob
from collections import defaultdict

def load_chase_statements(folder_path):
    """
    Load multiple CSV files from the specified folder and combine them into a single DataFrame.
    """
    files = glob.glob(f"{folder_path}/*.csv")
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
    folder_path = input("Enter the path to the folder containing your Chase statement CSV files: ")
    main(folder_path)
