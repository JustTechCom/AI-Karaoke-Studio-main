import tkinter as tk
from tkinter import messagebox
import threading

class PopupManager:
    """
    Manages popup notifications for button clicks and operation completions.
    Can be integrated with any tkinter-based application.
    """
    
    @staticmethod
    def show_start_popup(operation_name):
        """
        Shows a popup notification when an operation starts.
        
        Parameters:
        - operation_name: Name of the operation being started
        """
        messagebox.showinfo(
            title="İşlem Başlatıldı",
            message=f"{operation_name} işlemi başlatıldı."
        )
    
    @staticmethod
    def show_completion_popup(operation_name, success=True):
        """
        Shows a popup notification when an operation completes.
        
        Parameters:
        - operation_name: Name of the operation that completed
        - success: Whether the operation completed successfully
        """
        if success:
            messagebox.showinfo(
                title="İşlem Tamamlandı",
                message=f"{operation_name} işlemi başarıyla tamamlandı."
            )
        else:
            messagebox.showerror(
                title="İşlem Başarısız",
                message=f"{operation_name} işlemi sırasında bir hata oluştu."
            )
    
    @staticmethod
    def run_with_popups(operation_func, operation_name, *args, **kwargs):
        """
        Runs a function with start and completion popups.
        
        Parameters:
        - operation_func: Function to execute
        - operation_name: Name of the operation (for popup messages)
        - *args, **kwargs: Arguments to pass to the operation function
        
        Returns:
        - The result of the operation function
        """
        PopupManager.show_start_popup(operation_name)
        try:
            result = operation_func(*args, **kwargs)
            PopupManager.show_completion_popup(operation_name)
            return result
        except Exception as e:
            PopupManager.show_completion_popup(operation_name, success=False)
            raise e

    @staticmethod
    def run_async_with_popups(operation_func, operation_name, *args, **kwargs):
        """
        Runs a function asynchronously with start and completion popups.
        
        Parameters:
        - operation_func: Function to execute
        - operation_name: Name of the operation (for popup messages)
        - *args, **kwargs: Arguments to pass to the operation function
        """
        PopupManager.show_start_popup(operation_name)
        
        def wrapper():
            try:
                operation_func(*args, **kwargs)
                # Use after() to ensure the popup is shown from the main thread
                root = tk._default_root or tk.Tk()
                root.after(0, lambda: PopupManager.show_completion_popup(operation_name))
            except Exception as e:
                root = tk._default_root or tk.Tk()
                root.after(0, lambda: PopupManager.show_completion_popup(operation_name, success=False))
                print(f"Error in {operation_name}: {e}")
        
        thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
        return thread