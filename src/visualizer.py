import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


def generate_benchmark_reports(file_path):

    try:
        # CSV oku
        df = pd.read_csv(file_path)

        print(f"✅ Dosya başarıyla okundu: {file_path}")

        # Scenario parsing
        df['Orders'] = df['Scenario'].apply(lambda x: int(x.split('_')[0]))
        df['Max_Order_Lines'] = df['Scenario'].apply(lambda x: int(x.split('_')[1]))
        df['Max_Parts_Per_Line'] = df['Scenario'].apply(lambda x: int(x.split('_')[2]))

        grouped = df.groupby('Orders').mean(numeric_only=True).reset_index()

        sns.set_theme(style="whitegrid", context="talk")

        # ==========================================================
        # 1. DISTANCE COMPARISON
        # ==========================================================
        plt.figure(figsize=(14, 8))

        bar_data = grouped.melt(
            id_vars='Orders',
            value_vars=[
                'DEPSO_Avg',
                'SOP_Avg',
                'FCFS_Avg',
                'Savings_Avg'
            ],
            var_name='Method',
            value_name='Average Distance'
        )

        bar_data['Method'] = bar_data['Method'].replace({
            'DEPSO_Avg': 'DEPSO (Proposed)',
            'SOP_Avg': 'SOP',
            'FCFS_Avg': 'FCFS',
            'Savings_Avg': 'Savings'
        })

        sns.barplot(
            data=bar_data,
            x='Orders',
            y='Average Distance',
            hue='Method'
        )

        plt.title('Average Travel Distance Comparison', pad=20)
        plt.xlabel('Number of Orders')
        plt.ylabel('Average Distance (LU)')
        plt.legend(title='Method')

        plt.tight_layout()

        plt.savefig(
            'distance_comparison_full.png',
            dpi=300
        )

        # ==========================================================
        # 2. GAP ANALYSIS
        # ==========================================================
        plt.figure(figsize=(14, 8))

        plt.plot(
            grouped['Orders'],
            grouped['Gap_SOP_%'],
            marker='o',
            linewidth=3,
            label='Gap vs SOP'
        )

        plt.plot(
            grouped['Orders'],
            grouped['Gap_FCFS_%'],
            marker='s',
            linewidth=3,
            label='Gap vs FCFS'
        )

        plt.plot(
            grouped['Orders'],
            grouped['Gap_Savings_%'],
            marker='^',
            linewidth=3,
            label='Gap vs Savings'
        )

        plt.axhline(0, color='black', linestyle='--', alpha=0.3)

        plt.title('Performance Improvement Gap (%)', pad=20)
        plt.xlabel('Number of Orders')
        plt.ylabel('Improvement (%)')

        plt.legend()

        plt.grid(True, linestyle=':', alpha=0.6)

        plt.tight_layout()

        plt.savefig(
            'gap_analysis_full.png',
            dpi=300
        )

        # ==========================================================
        # 3. RUNTIME ANALYSIS
        # ==========================================================
        plt.figure(figsize=(14, 8))

        plt.plot(
            grouped['Orders'],
            grouped['Runtime_Avg'],
            marker='o',
            linewidth=3
        )

        plt.title('Runtime Growth by Order Size', pad=20)
        plt.xlabel('Number of Orders')
        plt.ylabel('Average Runtime (seconds)')

        plt.grid(True, linestyle=':', alpha=0.6)

        plt.tight_layout()

        plt.savefig(
            'runtime_analysis_full.png',
            dpi=300
        )

        print("\n✅ Tüm grafikler başarıyla oluşturuldu!")

        plt.show()

    except FileNotFoundError:
        print(f"❌ HATA: '{file_path}' dosyası bulunamadı!")

    except Exception as e:
        print(f"❌ Bir hata oluştu: {e}")


if __name__ == "__main__":

    target_file = "DEPSO_Full_35_Benchmark_With_Savings.csv"

    generate_benchmark_reports(target_file)