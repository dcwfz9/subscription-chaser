import pandas as pd
import glob
import argparse
import os
import json
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict

def load_exclusions(file_path):
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
    folder_path = os.path.abspath(folder_path)
    files = glob.glob(os.path.join(folder_path, "*.csv")) + glob.glob(os.path.join(folder_path, "*.CSV"))
    df_list = [pd.read_csv(file) for file in files]
    df = pd.concat(df_list, ignore_index=True).drop_duplicates()
    return df

def clean_data(df, exclusions, category):
    df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]
    df = df.rename(columns={
        'transaction_date': 'date',
        'description': 'vendor',
        'amount': 'charge'
    })
    df['date'] = pd.to_datetime(df['date'])
    df['charge'] = df['charge'].astype(float)
    df = df.drop_duplicates(subset=['date', 'vendor', 'charge'])
    
    df = df[~df['vendor'].str.lower().isin(exclusions[category]['vendors'])]
    df = df[~df['vendor'].str.lower().apply(lambda x: any(keyword in x for keyword in exclusions[category]['keywords']))]
    df = df[~df['charge'].isin(exclusions[category]['charges'])]
    
    return df[['date', 'vendor', 'charge']]

def find_recurring_charges(df):
    recurring_charges = defaultdict(lambda: defaultdict(lambda: {'total_spent': 0, 'months': set()}))
    
    grouped = df.groupby(['vendor', 'charge'])
    for (vendor, charge), transactions in grouped:
        months = set(transactions['date'].dt.to_period('M'))
        if len(months) > 2:
            total_spent = charge * len(months)
            recurring_charges[vendor][charge]['total_spent'] = total_spent
            recurring_charges[vendor][charge]['months'] = months
    
    sorted_recurring = sorted(
        [(vendor, charge, data['total_spent'], data['months'])
         for vendor, charges in recurring_charges.items() for charge, data in charges.items()],
        key=lambda x: x[2], reverse=True
    )
    return sorted_recurring

def flag_subscription_keywords(df):
    keywords = ['membership', 'subscription', 'renewal']
    df['flagged'] = df['vendor'].str.lower().apply(lambda x: any(keyword in x for keyword in keywords))
    return df[df['flagged']]

def top_vendors_by_spending(df, top_n=25):
    top_vendors = df.groupby('vendor')['charge'].sum().sort_values().head(top_n)
    return top_vendors.reset_index()

def most_expensive_charges(df, top_n=25):
    expensive_charges = df.nsmallest(top_n, 'charge')
    return expensive_charges[['vendor', 'charge']]

def print_results(recurring_charges, top_vendors, expensive_charges, flagged_subscriptions):
    print("\nRecurring Charges:")
    for vendor, charge, total_spent, months in sorted(recurring_charges, key=lambda x: x[2], reverse=True):
        print(f"{vendor}: ${charge:.2f} per month, Total Spent: ${total_spent:.2f}, Months: {len(months)}")
    
    print("\nTop Vendors by Spending:")
    print(top_vendors.to_string(index=False))
    
    print("\nMost Expensive Charges:")
    print(expensive_charges.to_string(index=False))
    
    print("\nFlagged Subscription Transactions:")
    print(flagged_subscriptions[['vendor', 'charge']].to_string(index=False))

def generate_summary_report(top_vendors, expensive_charges, recurring_charges, flagged_subscriptions):
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    recurring_df = pd.DataFrame(recurring_charges, columns=['Vendor', 'Charge', 'Total Spent', 'Months'])
    recurring_df = recurring_df.sort_values(by='Total Spent', ascending=True)
    sns.barplot(y=recurring_df['Vendor'], x=recurring_df['Total Spent'], hue=recurring_df['Vendor'], palette='Purples_r', ax=axes[0, 0], legend=False)
    axes[0, 0].set_title("Recurring Charges Sorted by Total Spent")
    
    flagged_subscriptions = flagged_subscriptions.sort_values(by='charge', ascending=True)
    sns.barplot(y=flagged_subscriptions['vendor'], x=flagged_subscriptions['charge'], hue=flagged_subscriptions['vendor'], palette='Blues_r', ax=axes[0, 1], legend=False)
    axes[0, 1].set_title("Flagged Subscription Transactions")
    
    sns.barplot(y=expensive_charges['vendor'], x=expensive_charges['charge'], hue=expensive_charges['vendor'], palette='Reds_r', ax=axes[1, 1], legend=False)
    axes[1, 1].set_title("Most Expensive Charges")
    
    sns.barplot(y=top_vendors['vendor'], x=top_vendors['charge'], hue=top_vendors['vendor'], palette='coolwarm', ax=axes[1, 0], legend=False)
    axes[1, 0].set_title("Top Vendors by Spending")
    
    plt.tight_layout()
    plt.show()

def main(folder_path, exclusion_file):
    exclusions = load_exclusions(exclusion_file)
    df = load_chase_statements(folder_path)
    
    df_recurring = clean_data(df, exclusions, 'recurring')
    recurring_charges = find_recurring_charges(df_recurring)
    
    df_spending = clean_data(df, exclusions, 'spending')
    top_vendors = top_vendors_by_spending(df_spending)
    expensive_charges = most_expensive_charges(df_spending)
    flagged_subscriptions = flag_subscription_keywords(df_spending)
    
    print_results(recurring_charges, top_vendors, expensive_charges, flagged_subscriptions)
    generate_summary_report(top_vendors, expensive_charges, recurring_charges, flagged_subscriptions)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze Chase credit card statements.")
    parser.add_argument("--folder_path", type=str, default="statements")
    parser.add_argument("--exclusion_file", type=str, default="exclusions.json")
    args = parser.parse_args()
    
    main(args.folder_path, args.exclusion_file)
