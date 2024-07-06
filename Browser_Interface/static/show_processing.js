$(document).ready(
    function(){
        const submitBtns = document.getElementsByClassName("showProcessing");
        for (let i = 0; i < submitBtns.length; i++) {
            let btn = submitBtns[i];
            btn.addEventListener("click", function() {
                //btn.disabled = true;
                btn.value = "Processing...";
                btn.form.submit();
            });
        }
    }
);