#include <iostream>
#include <vector>
#include <time.h>
#include <cmath>
#include <stdlib.h>
#include <string>
#include <istream>
#include <fstream>
#include <sstream>


using namespace std;

class Task {
public: std::string name;
	  std::string desc;
	  bool complete;

	  //constructor
	  Task(const std::string& taskName, const std::string& taskDesc)
		  : name(taskName), desc(desc), complete(false) {}

};

class TaskManager {
private:
	std::vector<Task> tasks;

public:
	void addTask(const Task& task) // add a task
	{
		tasks.push_back(task);
	}
	void comTask(int index) //mark task as complete 
	{
		if (index >= 0 && index < tasks.size())
		{
			tasks[index].complete = true;
			std::cout << "Tasks marked as complete: " << tasks[index].name << "\n";
		}
		else {
			std::cout << "Invalid task index.\n";
		}
	}
	void displayTask() //show tasks
	{
		std::cout << "Tasks: \n";
		for (size_t i = 0; i < tasks.size(); i++)
		{
			std::cout << "[" << i + 1 << "] " << tasks[i].name;
			if (tasks[i].complete)
			{
				std::cout << "(Completed)";
			}
			std::cout << "\n";
		}
	}
	void saveTask(const std::string& filename) //save task to file
	{
		std::ofstream outFile(filename);
		if (outFile.is_open()) {
			for (const auto& task : tasks) {
				outFile << task.name << "," << task.desc << "," << task.complete << "\n";
			}
			std::cout << "Tasks saved to file: " << filename << "\n";
			outFile.close();
		}
		else {
			std::cout << "Unable to open file for writing.\n";
		}
	}


	void loadTasks(const std::string& filename) { //load task from file
		std::ifstream inFile(filename);
		if (inFile.is_open()) {
			tasks.clear(); // Clear existing tasks

			std::string line;
			while (std::getline(inFile, line)) {
				std::istringstream iss(line);
				std::string taskName, taskDescription, completedStr;

				if (std::getline(iss, taskName, ',') &&
					std::getline(iss, taskDescription, ',') &&
					std::getline(iss, completedStr)) {

					bool completed = (completedStr == "1");
					Task task(taskName, taskDescription);
					task.complete = completed;
					tasks.push_back(task);
				}
			}
			std::cout << "Tasks loaded from file: " << filename << "\n";
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
	TaskManager taskManager; 

	//interface
	cout << "Welcome to your Task Manager! \n\n";
	std::string filename;
	cout << "Enter filename to save Tasks: \n";
	cin >> filename;
	taskManager.saveTask(filename); //creates file to save task list to

	while(true)
	{
		cout << "\nWelcome to your Task Manager! \n";
		cout << "Please select an Option: \n";
		cout << "1. Add a Task \n";
		cout << "2. Mark a Task complete \n";
		cout << "3. View Task List \n";
		cout << "4. Save Task List \n";
		cout << "5. Load Task List \n";
		cout << "6. Close Manager \n";
		cin >> option;
		cout << "\n\n";

		switch (option) {
		case 1: { //add task
			string taskName, taskDesc;
			cout << "Enter task name: ";
			
			cin.ignore(); // Clear the input buffer
			getline(std::cin, taskName);
			cout << "Enter task description: ";
			getline(std::cin, taskDesc);
			
			Task newTask(taskName, taskDesc);
			taskManager.addTask(newTask);
			break;
		}
		case 2: { //mark task complete
			int taskIndex;
			std::cout << "Enter the task index to mark as completed: ";
			std::cin >> taskIndex;
			taskManager.comTask(taskIndex - 1); // Adjust for 0-based indexing
			break;
		}
		case 3: { //view task
			taskManager.displayTask();
			break;
		}
		case 4: { //save task list
			std::string filename;
			cout << "Enter filename to save Tasks: \n";
			cin >> filename;
			taskManager.saveTask(filename);
			break;
		}
		case 5: { //load task list
			std::string filename;
			cout << "Enter filename to Load Tasks: \n";
			cin >> filename;
			taskManager.loadTasks(filename);
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