//created by Colin Castlewitz

#include <iostream>
#include <string>
#include <fstream>
#include <istream>
#include <sstream>
#include <vector>

using namespace std;

class Expense {
public:
	string date;
	string category;
	double amount;
	bool paid;

	//constructor
	Expense(const std::string& expDate, const std::string& expCat, const double& expAmount)
		: date(expDate), category(expCat), amount(expAmount), paid(false) {}
};

class ExpenseManager {
private:
	vector<Expense> expenses;
public:
	void addExpense(const Expense& expense)
	{
		expenses.push_back(expense);
	}
	void displayExpense()
	{
		cout << "Expenses: \n";
		for (size_t i = 0; i < expenses.size(); i++)
		{
			cout << "[" << i + 1 << "] " << expenses[i].category << ": $" << expenses[i].amount;
			if (expenses[i].paid)
			{
				cout << "(Paid off)";
			}
			cout << "\n";
		}
	}
	void deleteExpense(int index)
	{
		if (index >= 0 && index < expenses.size())
		{
			expenses[index].paid = true;
			std::cout << "Expenses marked as complete: " << expenses[index].category << "\n";
		}
		else {
			std::cout << "Invalid expense index.\n";
		}
	}
	void saveExpense(const std::string& filename)
	{
		std::ofstream outFile(filename);
		if (outFile.is_open()) {
			for (const auto& expense : expenses) {
				outFile << expense.category << "," << expense.date << "," << expense.amount <<  "," << expense.paid << "\n";
			}
			std::cout << "Expenses saved to file: " << filename << "\n";
			outFile.close();
		}
		else {
			std::cout << "Unable to open file for writing.\n";
		}
	}
	void loadExpense(const std::string& filename)
	{
		std::ifstream inFile(filename);
		if (inFile.is_open()) {
			expenses.clear(); // Clear existing expenses

			std::string line;
			while (std::getline(inFile, line)) {
				std::istringstream iss(line);
				std::string expDate, expCat, paidStr;
				double expAmount;

				if (std::getline(iss, expCat, ',') &&
					std::getline(iss, expDate, ',') &&
					std::getline(iss, paidStr)) {

					bool completed = (paidStr == "1");
					Expense expenselist(expDate, expCat, expAmount);
					expenselist.paid = completed;
					expenses.push_back(expenselist);
				}
			}
			std::cout << "Expenses loaded from file: " << filename << "\n";
			inFile.close();
		}
		else {
			std::cout << "Unable to open file for reading.\n";
		}
	}
	
};


int main()
{
	//declare variables
	int option = 0;
	ExpenseManager expenseManager;

	//interface
	cout << "Welcome to your Expense Tracker! \n\n";
	std::string filename;
	cout << "Enter filename to save Expenses: \n";
	cin >> filename;
	expenseManager.saveExpense(filename); //creates file to save expense list to

	while (true)
	{
		cout << "\nWelcome to your Expense Tracker! \n";
		cout << "Please select an Option: \n";
		cout << "1. Add a Expense \n";
		cout << "2. Mark a Expense as Paid \n";
		cout << "3. View Expense List \n";
		cout << "4. Save Expense List \n";
		cout << "5. Load Expense List \n";
		cout << "6. Close Expense tracker \n";
		cin >> option;
		cout << "\n\n";

		switch (option) {
		case 1: { //add expense
			string expCat, expDate;
			double expAmount;
			cout << "Enter Expense Category: ";
			cin.ignore(); // Clear the input buffer
			getline(std::cin, expCat);
			cout << "Enter Expense date: ";
			getline(std::cin, expDate);
			cout << "Enter Expense Amount: ";
			cin >> expAmount;

			Expense newExpense(expDate, expCat, expAmount);
			expenseManager.addExpense(newExpense);
			break;
		}
		case 2: { //delete expenses
			int expIndex;
			std::cout << "Enter the expense index to mark as paid: ";
			std::cin >> expIndex;
			expenseManager.deleteExpense(expIndex - 1); // Adjust for 0-based indexing
			break;
		}
		case 3: { //view expenses
			expenseManager.displayExpense();
			break;
		}
		case 4: { //save expense list
			std::string filename;
			cout << "Enter filename to save Expenses: \n";
			cin >> filename;
			expenseManager.saveExpense(filename);
			break;
		}
		case 5: { //load expense list
			std::string filename;
			cout << "Enter filename to Load Expenses: \n";
			cin >> filename;
			expenseManager.loadExpense(filename);
			break;
		}
		case 6: { //close manager
			cout << "Closing manager... \n";
			return 0;
		}
		default: {
			cout << "Invalid choice, please choose another option. \n\n";
		}
		}
	}
	//Exit 
	cout << "Thank you! Program shutting down...\n";

	return 0;
}

// Run program: Ctrl + F5 or Debug > Start Without Debugging menu
// Debug program: F5 or Debug > Start Debugging menu

// Tips for Getting Started: 
//   1. Use the Solution Explorer window to add/manage files
//   2. Use the Team Explorer window to connect to source control
//   3. Use the Output window to see build output and other messages
//   4. Use the Error List window to view errors
//   5. Go to Project > Add New Item to create new code files, or Project > Add Existing Item to add existing code files to the project
//   6. In the future, to open this project again, go to File > Open > Project and select the .sln file
