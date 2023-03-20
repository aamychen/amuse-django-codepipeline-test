$(document).ready(function() {
    var progress = $('#replace-file-progress')
    progress.hide().css({width:'91%'})

    $('.replace-audio-file-input').each(function() {
        var self = $(this)
        var form = self.parent('form')
        self.filer({
            uploadFile: {
                type: 'POST',
                limit: 1,
                extensions: ["wav"],
                success: function(res) {
                    progress.hide()
                    $('#replace-audio-file-messages').append('<li class="success">Your file was successfully uploaded</li>')
                    $.post(form.data('complete-url'), {key: this.data.key})
                },
                error: function(res) {
                    console.log(res)
                },
                onProgress: function(res) {
                    progress[0].value = res
                }
            },
            beforeSelect: function() {
                res = $.ajax({
                    type: 'POST',
                    url: form.data('prepare-url'),
                    async: false,
                }).responseJSON
                this.uploadFile.url = res.url
                this.uploadFile.data = res.fields

                progress.show()

                return true
            },
            afterRender: function() {
                self.attr('name', 'file')
            }
        })
    })
})
